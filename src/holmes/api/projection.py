from datetime import date
from typing import Any, Callable

import numpy as np
import numpy.typing as npt
import polars as pl
from holmes_rs.pet import oudin
from starlette.routing import BaseRoute, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from holmes import data
from holmes.logging import logger
from holmes.models import hydro, snow
from holmes.utils.print import format_list

from .utils import send

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
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            await _handle_message(ws, msg)
    except WebSocketDisconnect:
        pass


async def _handle_message(ws: WebSocket, msg: dict[str, Any]) -> None:
    logger.info(f"Websocket {msg.get('type')} message")
    match msg.get("type"):
        case "config":
            if "data" not in msg:
                await send(ws, "error", "The catchment must be provided.")
                return
            await _handle_config_message(ws, msg["data"])
        case "projection":
            await _handle_projection_message(ws, msg.get("data", {}))
        case _:
            await send(ws, "error", f"Unknown message type {msg['type']}.")


async def _handle_config_message(ws: WebSocket, msg_data: str) -> None:
    config = (
        data.read_projection_data(msg_data)
        .select("model", "horizon", "scenario")
        .unique()
        .sort("model", "horizon", "scenario")
        .collect()
    )
    await send(ws, "config", config)


async def _handle_projection_message(
    ws: WebSocket, msg_data: dict[str, Any]
) -> None:
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
    metadata = data.read_cemaneige_info(catchment)
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

    elevation_layers = np.array(metadata["altitude_layers"])
    median_elevation = metadata["median_altitude"]
    latitude = metadata["latitude"]
    qnbv = metadata["qnbv"]

    hydro_simulate = hydro.get_model(msg_data["calibration"]["hydroModel"])
    hydro_params = np.array(
        list(msg_data["calibration"]["hydroParams"].values())
    )

    snow_simulate = (
        snow.get_model(msg_data["calibration"]["snowModel"])
        if msg_data["calibration"]["snowModel"] is not None
        else None
    )
    snow_params = np.array([0.25, 3.74, qnbv])

    projections = [
        _run_projection(
            member_data,
            elevation_layers,
            median_elevation,
            latitude,
            hydro_simulate,
            snow_simulate,
            hydro_params,
            snow_params,
        ).rename({"streamflow": f"member_{member_data[0, 'member']}"})
        for member_data in _data.partition_by("member", maintain_order=True)
    ]
    projection = (
        pl.concat(
            [
                projections[0],
                *[p.drop("day_of_year") for p in projections[1:]],
            ],
            how="horizontal",
        )
        .with_columns(
            pl.lit(date(2021, 1, 1)).alias("date")
            + pl.duration(days=pl.col("day_of_year") - 1)
        )
        .drop("day_of_year")
    )
    projection = projection.with_columns(
        projection.unpivot(
            index="date",
        )
        .group_by("date")
        .agg(pl.col("value").median().alias("median"))
        .sort("date")["median"]
    )

    await send(
        ws,
        "projection",
        projection,
    )


###########
# private #
###########


def _run_projection(
    _data: pl.DataFrame,
    elevation_layers: npt.NDArray[np.float64],
    median_elevation: float,
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
    snow_params: npt.NDArray[np.float64],
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
        precipitation = snow_simulate(
            snow_params,
            precipitation,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )

    _data = (
        pl.DataFrame(
            {
                "day_of_year": day_of_year,
                "streamflow": hydro_simulate(hydro_params, precipitation, pet),
            }
        )
        .group_by("day_of_year")
        .agg(pl.col("streamflow").mean())
        .sort("day_of_year")
    )

    return _data
