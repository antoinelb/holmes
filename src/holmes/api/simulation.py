from typing import Any, cast

import numpy as np
import numpy.typing as npt
import polars as pl
from holmes import data
from holmes.exceptions import HolmesDataError
from holmes.logging import logger
from holmes.models import hydro, snow
from holmes.models.utils import evaluate
from holmes.utils.print import format_list
from holmes.utils.websocket import cleanup_websocket, send
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
        logger.debug("Simulation WebSocket client disconnected")
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
        case "observations":
            await _handle_observations_message(ws, msg.get("data", {}))
        case "simulation":
            await _handle_simulation_message(ws, msg.get("data", {}))
        case _:
            await send(ws, "error", f"Unknown message type {msg_type}.")


async def _handle_config_message(ws: WebSocket, msg_data: str) -> None:
    """Handle config request - return date range for catchment."""
    try:
        catchment = next(
            c for c in data.get_available_catchments() if c[0] == msg_data
        )
    except StopIteration:
        await send(ws, "error", f"Unknown catchment {msg_data}.")
        return

    config = {"start": catchment[2][0], "end": catchment[2][1]}
    await send(ws, "config", config)


async def _handle_observations_message(
    ws: WebSocket, msg_data: dict[str, Any]
) -> None:
    """Handle observations request - return streamflow data for date range."""
    needed_keys = [
        "catchment",
        "start",
        "end",
    ]
    if any(key not in msg_data for key in needed_keys):
        await send(
            ws,
            "error",
            format_list(needed_keys, surround="`") + " must be provided.",
        )
        return

    try:
        _data, _ = data.read_data(
            msg_data["catchment"], msg_data["start"], msg_data["end"]
        )
    except HolmesDataError as exc:
        await send(ws, "error", str(exc))
        return

    await send(ws, "observations", _data.select("date", "streamflow"))


async def _handle_simulation_message(
    ws: WebSocket, msg_data: dict[str, Any]
) -> None:
    """Handle simulation request - run forward model with calibrated parameters."""
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
    if len(msg_data["calibration"]) == 0:
        await send(
            ws, "error", "At least one calibration config must be provided."
        )
        return
    if (
        msg_data["config"]["start"] is None
        or msg_data["config"]["end"] is None
    ):
        await send(
            ws, "error", "`start` or `end` must be provided in the config."
        )
        return

    catchment = msg_data["calibration"][0]["catchment"]
    start = msg_data["config"]["start"]
    end = msg_data["config"]["end"]

    try:
        _data, warmup_steps = data.read_data(catchment, start, end)
    except HolmesDataError as exc:
        await send(ws, "error", str(exc))
        return

    # Check if any calibration uses a snow model
    uses_snow = any(
        calibration["snowModel"] is not None
        for calibration in msg_data["calibration"]
    )

    if uses_snow:
        try:
            metadata = data.read_cemaneige_info(catchment)
        except HolmesDataError as exc:
            await send(ws, "error", str(exc))
            return
        try:
            temperature = _data["temperature"].to_numpy()
        except pl.exceptions.ColumnNotFoundError:
            await send(
                ws,
                "error",
                f"The {catchment} catchment doesn't have any temperature data.",
            )
            return
        elevation_layers = np.array(metadata["altitude_layers"])
        median_elevation = metadata["median_altitude"]
        qnbv = metadata["qnbv"]
    else:
        temperature = None
        elevation_layers = None
        median_elevation = None
        qnbv = None

    precipitation = _data["precipitation"].to_numpy()
    pet = _data["pet"].to_numpy()
    day_of_year = (
        _data.select((pl.col("date").dt.ordinal_day() - 1).mod(365) + 1)[
            "date"
        ]
        .to_numpy()
        .astype(np.uintp)
    )

    observations = _data["streamflow"].to_numpy()

    simulations = [
        _run_simulation(
            precipitation,
            temperature,
            pet,
            day_of_year,
            elevation_layers,
            median_elevation,
            qnbv,
            observations,
            calibration["hydroModel"],
            calibration["snowModel"],
            calibration["hydroParams"],
            warmup_steps,
        )
        for calibration in msg_data["calibration"]
    ]

    simulation = _data.select("date").with_columns(
        *[
            pl.Series(f"simulation_{i+1}", simulation)
            for i, (simulation, _) in enumerate(simulations)
        ]
    )
    results = [
        {"name": f"simulation_{i+1}", **results}
        for i, (_, results) in enumerate(simulations)
    ]

    if msg_data["config"]["multimodel"]:
        simulation = simulation.with_columns(
            pl.mean_horizontal(pl.exclude("date")).alias("multimodel")
        )
        streamflow = simulation["multimodel"].to_numpy()
        observations_evaluated = observations[warmup_steps:]
        streamflow_evaluated = streamflow[warmup_steps:]
        results.append(
            {
                "name": "multimodel",
                "nse_none": evaluate(
                    observations_evaluated, streamflow_evaluated, "nse", "none"
                ),
                "nse_sqrt": evaluate(
                    observations_evaluated, streamflow_evaluated, "nse", "sqrt"
                ),
                "nse_log": evaluate(
                    observations_evaluated, streamflow_evaluated, "nse", "log"
                ),
                "mean_bias": evaluate(
                    observations_evaluated,
                    streamflow_evaluated,
                    "mean_bias",
                    "none",
                ),
                "deviation_bias": evaluate(
                    observations_evaluated,
                    streamflow_evaluated,
                    "deviation_bias",
                    "none",
                ),
                "correlation": evaluate(
                    observations_evaluated,
                    streamflow_evaluated,
                    "correlation",
                    "none",
                ),
            }
        )

    await send(
        ws,
        "simulation",
        {
            "simulation": simulation,
            "results": results,
        },
    )


###########
# private #
###########


def _run_simulation(
    precipitation: npt.NDArray[np.float64],
    temperature: npt.NDArray[np.float64] | None,
    pet: npt.NDArray[np.float64],
    day_of_year: npt.NDArray[np.uintp],
    elevation_layers: npt.NDArray[np.float64] | None,
    median_elevation: float | None,
    qnbv: float | None,
    observations: npt.NDArray[np.float64],
    hydro_model: str,
    snow_model: str | None,
    hydro_params: dict[str, float],
    warmup_steps: int,
) -> tuple[npt.NDArray[np.float64], dict[str, float]]:

    hydro_simulate = hydro.get_model(cast(hydro.HydroModel, hydro_model))
    hydro_params_ = np.array(list(hydro_params.values()))

    if snow_model is not None:
        # These values are guaranteed to be non-None when snow_model is set
        assert temperature is not None
        assert elevation_layers is not None
        assert median_elevation is not None
        assert qnbv is not None
        snow_simulate = snow.get_model(cast(snow.SnowModel, snow_model))
        snow_params = np.array([0.25, 3.74, qnbv])
        precipitation = snow_simulate(
            snow_params,
            precipitation,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )

    streamflow = hydro_simulate(hydro_params_, precipitation, pet)

    observations_evaluated = observations[warmup_steps:]
    streamflow_evaluated = streamflow[warmup_steps:]

    results = {
        "nse_none": evaluate(
            observations_evaluated, streamflow_evaluated, "nse", "none"
        ),
        "nse_sqrt": evaluate(
            observations_evaluated, streamflow_evaluated, "nse", "sqrt"
        ),
        "nse_log": evaluate(
            observations_evaluated, streamflow_evaluated, "nse", "log"
        ),
        "mean_bias": evaluate(
            observations_evaluated, streamflow_evaluated, "mean_bias", "none"
        ),
        "deviation_bias": evaluate(
            observations_evaluated,
            streamflow_evaluated,
            "deviation_bias",
            "none",
        ),
        "correlation": evaluate(
            observations_evaluated, streamflow_evaluated, "correlation", "none"
        ),
    }

    return streamflow, results
