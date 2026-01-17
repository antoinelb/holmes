from datetime import date
from typing import Any, Callable

import numpy as np
import numpy.typing as npt
import polars as pl
from holmes import data
from holmes.exceptions import HolmesDataError
from holmes.logging import logger
from holmes.models import hydro, snow
from holmes.utils.print import format_list
from holmes.utils.websocket import cleanup_websocket, send
from holmes_rs.pet import oudin
from starlette.routing import BaseRoute, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

##########
# public #
##########


def get_routes() -> list[BaseRoute]:
    return [
        WebSocketRoute("/", endpoint=_websocket_handler),
    ]


##########
# routes #
##########


async def _websocket_handler(ws: WebSocket) -> None:
    """Main WebSocket handler with connection lifecycle management."""
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            await _handle_message(ws, msg)
    except WebSocketDisconnect:
        # P1-ERR-04: Log disconnection instead of silent pass
        logger.debug("Projection WebSocket client disconnected")
    finally:
        # P3-WS-05: Clean up connection state
        await cleanup_websocket(ws)


async def _handle_message(ws: WebSocket, msg: dict[str, Any]) -> None:
    """Dispatch incoming WebSocket messages to handlers."""
    msg_type = msg.get("type")
    logger.info(f"Websocket {msg_type} message")

    match msg_type:
        case "config":
            if "data" not in msg:
                await send(ws, "error", "The catchment must be provided.")
                return
            await _handle_config_message(ws, msg["data"])
        case "projection":
            await _handle_projection_message(ws, msg.get("data", {}))
        case _:
            await send(ws, "error", f"Unknown message type {msg_type}.")


async def _handle_config_message(ws: WebSocket, msg_data: str) -> None:
    """Handle config request - return available projection configurations."""
    try:
        config = (
            data.read_projection_data(msg_data)
            .select("model", "horizon", "scenario")
            .unique()
            .sort("model", "horizon", "scenario")
            .collect()
        )
    except HolmesDataError as exc:
        await send(ws, "error", str(exc))
        return

    await send(ws, "config", config)


async def _handle_projection_message(
    ws: WebSocket, msg_data: dict[str, Any]
) -> None:
    """Handle projection request - run climate projection simulation."""
    needed_keys = [
        "config",
        "calibration",
    ]
    if any(key not in msg_data for key in needed_keys):
        await send(
            ws,
            "error",
            format_list(needed_keys, surround="`") + " must be provided.",
        )
        return

    catchment = msg_data["calibration"]["catchment"]

    try:
        _data = (
            data.read_projection_data(catchment)
            .filter(
                pl.col("model") == msg_data["config"]["model"],
                pl.col("horizon") == msg_data["config"]["horizon"],
                pl.col("scenario") == msg_data["config"]["scenario"],
            )
            .sort("member")
            .collect()
        )
        # CemaNeige info is always needed for latitude (PET calculation)
        metadata = data.read_cemaneige_info(catchment)
    except HolmesDataError as exc:
        await send(ws, "error", str(exc))
        return

    latitude = metadata["latitude"]

    # Only set up snow parameters when snow model is used
    if msg_data["calibration"]["snowModel"] is not None:
        elevation_layers = np.array(metadata["altitude_layers"])
        median_elevation = metadata["median_altitude"]
        qnbv = metadata["qnbv"]
        snow_simulate = snow.get_model(msg_data["calibration"]["snowModel"])
        snow_params = np.array([0.25, 3.74, qnbv])
    else:
        elevation_layers = None
        median_elevation = None
        snow_simulate = None
        snow_params = None

    hydro_simulate = hydro.get_model(msg_data["calibration"]["hydroModel"])
    hydro_params = np.array(
        list(msg_data["calibration"]["hydroParams"].values())
    )

    projection = pl.concat(
        [
            _run_projection(
                member_data,
                elevation_layers,
                median_elevation,
                latitude,
                hydro_simulate,
                snow_simulate,
                hydro_params,
                snow_params,
            ).with_columns(pl.lit(member_data[0, "member"]).alias("member"))
            for member_data in _data.partition_by("member")
        ]
    )
    results = _evaluate_projection(projection)
    projection = _aggregate_projections(projection)

    await send(
        ws,
        "projection",
        {"projection": projection, "results": results},
    )


###########
# private #
###########


def _run_projection(
    _data: pl.DataFrame,
    elevation_layers: npt.NDArray[np.float64] | None,
    median_elevation: float | None,
    latitude: float,
    hydro_simulate: Callable[
        [
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
        ],
        npt.NDArray[np.float64],
    ],
    snow_simulate: (
        Callable[
            [
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
                npt.NDArray[np.uintp],
                npt.NDArray[np.float64],
                float,
            ],
            npt.NDArray[np.float64],
        ]
        | None
    ),
    hydro_params: npt.NDArray[np.float64],
    snow_params: npt.NDArray[np.float64] | None,
) -> pl.DataFrame:
    precipitation = _data["precipitation"].to_numpy()
    temperature = _data["temperature"].to_numpy()
    day_of_year = (
        _data.select((pl.col("date").dt.ordinal_day() - 1).mod(365) + 1)[
            "date"
        ]
        .to_numpy()
        .astype(np.uintp)
    )

    pet = oudin.simulate(temperature, day_of_year, latitude)

    if snow_simulate is not None:
        # These values are guaranteed to be non-None when snow_simulate is set
        assert snow_params is not None
        assert elevation_layers is not None
        assert median_elevation is not None
        precipitation = snow_simulate(
            snow_params,
            precipitation,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )

    return _data.select("date").with_columns(
        pl.Series(
            "streamflow", hydro_simulate(hydro_params, precipitation, pet)
        )
    )


def _aggregate_projections(_data: pl.DataFrame) -> pl.DataFrame:
    _data = (
        _data.with_columns(
            ((pl.col("date").dt.ordinal_day() - 1).mod(365) + 1).alias(
                "day_of_year"
            )
        )
        .drop("date")
        .group_by("member", "day_of_year")
        .agg(pl.col("streamflow").mean())
    )
    return (
        _data.pivot(index="day_of_year", on="member", values="streamflow")
        .join(
            _data.group_by("day_of_year").agg(
                pl.col("streamflow").median().alias("median")
            ),
            on="day_of_year",
        )
        .with_columns(
            pl.lit(date(2021, 1, 1)).alias("date")
            + pl.duration(days=pl.col("day_of_year") - 1)
        )
        .drop("day_of_year")
        .sort("date")
    )


def _evaluate_projection(_data: pl.DataFrame) -> pl.DataFrame:
    winter_min = (
        _data.filter(pl.col("date").dt.month().is_between(1, 3))
        .group_by("member", pl.col("date").dt.year())
        .agg(pl.col("streamflow").min())
        .group_by("member")
        .agg(pl.col("streamflow").median().alias("winter_min"))
    )
    summer_min = (
        _data.filter(pl.col("date").dt.month().is_between(5, 10))
        .group_by("member", pl.col("date").dt.year())
        .agg(pl.col("streamflow").min())
        .group_by("member")
        .agg(pl.col("streamflow").median().alias("summer_min"))
    )
    spring_max = (
        _data.filter(pl.col("date").dt.month().is_between(3, 6))
        .group_by("member", pl.col("date").dt.year())
        .agg(pl.col("streamflow").max())
        .group_by("member")
        .agg(pl.col("streamflow").median().alias("spring_max"))
    )
    autumn_max = (
        _data.filter(pl.col("date").dt.month().is_between(9, 12))
        .group_by("member", pl.col("date").dt.year())
        .agg(pl.col("streamflow").max())
        .group_by("member")
        .agg(pl.col("streamflow").median().alias("autumn_max"))
    )
    mean = _data.group_by("member").agg(
        pl.col("streamflow").mean().alias("mean")
    )
    return (
        winter_min.join(summer_min, on="member")
        .join(spring_max, on="member")
        .join(autumn_max, on="member")
        .join(mean, on="member")
        .sort("member")
    )
