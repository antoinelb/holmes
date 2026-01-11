import asyncio
from typing import Any, get_args

import numpy as np
import numpy.typing as npt
import polars as pl
from starlette.routing import BaseRoute, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from holmes import data
from holmes.exceptions import HolmesDataError
from holmes.logging import logger
from holmes.models import calibration, evaluate, hydro, snow
from holmes.utils.print import format_list
from holmes.utils.websocket import (
    cleanup_websocket,
    create_monitored_task,
    send,
)


##########
# public #
##########


def get_routes() -> list[BaseRoute]:
    """Get routes for calibration WebSocket endpoint."""
    return [
        WebSocketRoute("/", endpoint=_websocket_handler),
    ]


async def _websocket_handler(ws: WebSocket) -> None:
    """Main WebSocket handler with connection lifecycle management."""
    await ws.accept()
    try:
        while True:
            msg = await ws.receive_json()
            await _handle_message(ws, msg)
    except WebSocketDisconnect:
        # P1-ERR-04: Log disconnection instead of silent pass
        logger.debug("Calibration WebSocket client disconnected")
    finally:
        # P3-WS-05: Clean up connection state
        await cleanup_websocket(ws)


async def _handle_message(ws: WebSocket, msg: dict[str, Any]) -> None:
    """Dispatch incoming WebSocket messages to handlers."""
    msg_type = msg.get("type")
    logger.info(f"Websocket {msg_type} message")

    match msg_type:
        case "config":
            await _handle_config_message(ws)
        case "observations":
            await _handle_observations_message(ws, msg.get("data", {}))
        case "manual":
            await _handle_manual_calibration_message(ws, msg.get("data", {}))
        case "calibration_start":
            stop_event = asyncio.Event()
            setattr(ws.state, "stop_event", stop_event)
            # P1-ERR-06: Use monitored task for error handling
            create_monitored_task(
                _handle_calibration_start_message(
                    ws, msg.get("data", {}), stop_event
                ),
                ws,
                task_name="calibration",
            )
        case "calibration_stop":
            if hasattr(ws.state, "stop_event"):
                getattr(ws.state, "stop_event").set()
        case _:
            await send(ws, "error", f"Unknown message type {msg_type}.")


async def _handle_config_message(ws: WebSocket) -> None:
    """Handle config request - return available models and catchments."""
    catchments = [
        {
            "name": c[0],
            "snow": c[1],
            "start": c[2][0],
            "end": c[2][1],
        }
        for c in data.get_available_catchments()
    ]
    config = {
        "hydro_model": [
            {"name": model, "params": hydro.get_config(model)}
            for model in get_args(hydro.HydroModel)
        ],
        "catchment": catchments,
        "snow_model": [None, *get_args(snow.SnowModel)],
        "objective": get_args(calibration.Objective),
        "transformation": get_args(calibration.Transformation),
        "algorithm": [
            {"name": "manual"},
            *[
                {
                    "name": algorithm,
                    "params": calibration.get_config(algorithm),
                }
                for algorithm in get_args(calibration.Algorithm)
            ],
        ],
    }
    await send(ws, "config", config)


async def _handle_observations_message(
    ws: WebSocket, msg_data: dict[str, Any]
) -> None:
    """Handle observations request - return streamflow data for date range."""
    if any(key not in msg_data for key in ("catchment", "start", "end")):
        await send(
            ws,
            "error",
            "`catchment`, `start` and `end` must be provided.",
        )
        return

    try:
        _data = data.read_data(
            msg_data["catchment"], msg_data["start"], msg_data["end"]
        )
    except HolmesDataError as exc:
        await send(ws, "error", str(exc))
        return

    await send(ws, "observations", _data.select("date", "streamflow"))


async def _handle_manual_calibration_message(
    ws: WebSocket, msg_data: dict[str, Any]
) -> None:
    """Handle manual calibration - simulate with user-provided parameters."""
    needed_keys = [
        "catchment",
        "start",
        "end",
        "hydroModel",
        "snowModel",
        "hydroParams",
        "objective",
        "transformation",
    ]
    if any(key not in msg_data for key in needed_keys):
        await send(
            ws,
            "error",
            format_list(needed_keys, surround="`") + " must be provided.",
        )
        return

    try:
        _data = data.read_data(
            msg_data["catchment"], msg_data["start"], msg_data["end"]
        )
        metadata = data.read_cemaneige_info(msg_data["catchment"])
    except HolmesDataError as exc:
        await send(ws, "error", str(exc))
        return

    hydro_simulate = hydro.get_model(msg_data["hydroModel"])
    hydro_params = np.array(msg_data["hydroParams"])

    precipitation = _data["precipitation"].to_numpy()
    temperature = _data["temperature"].to_numpy()
    pet = _data["pet"].to_numpy()
    day_of_year = (
        _data.select((pl.col("date").dt.ordinal_day() - 1).mod(365) + 1)[
            "date"
        ]
        .to_numpy()
        .astype(np.uintp)
    )
    elevation_layers = np.array(metadata["altitude_layers"])
    median_elevation = metadata["median_altitude"]

    observations = _data["streamflow"].to_numpy()

    if msg_data["snowModel"] is not None:
        snow_simulate = snow.get_model(msg_data["snowModel"])
        snow_params = np.array([0.25, 3.74, metadata["qnbv"]])
        precipitation = snow_simulate(
            snow_params,
            precipitation,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )

    streamflow = hydro_simulate(hydro_params, precipitation, pet)

    _data = _data.select("date").with_columns(
        pl.Series("streamflow", streamflow)
    )

    objective = evaluate(
        observations,
        streamflow,
        msg_data["objective"],
        msg_data["transformation"],
    )

    await send(
        ws,
        "result",
        {
            "done": True,
            "simulation": _data.select("date", "streamflow"),
            "params": hydro_params,
            "objective": objective,
        },
    )


async def _handle_calibration_start_message(
    ws: WebSocket, msg_data: dict[str, Any], stop_event: asyncio.Event
) -> None:
    """Handle automatic calibration - run SCE-UA optimization."""
    needed_keys = [
        "catchment",
        "start",
        "end",
        "hydroModel",
        "snowModel",
        "objective",
        "transformation",
        "algorithm",
        "algorithmParams",
    ]
    if any(key not in msg_data for key in needed_keys):
        await send(
            ws,
            "error",
            format_list(needed_keys, surround="`") + " must be provided.",
        )
        return

    try:
        _data = data.read_data(
            msg_data["catchment"], msg_data["start"], msg_data["end"]
        )
        metadata = data.read_cemaneige_info(msg_data["catchment"])
    except HolmesDataError as exc:
        await send(ws, "error", str(exc))
        return

    precipitation = _data["precipitation"].to_numpy()
    temperature = _data["temperature"].to_numpy()
    pet = _data["pet"].to_numpy()
    day_of_year = (
        _data.select((pl.col("date").dt.ordinal_day() - 1).mod(365) + 1)[
            "date"
        ]
        .to_numpy()
        .astype(np.uintp)
    )
    elevation_layers = np.array(metadata["altitude_layers"])
    median_elevation = metadata["median_altitude"]

    observations = _data["streamflow"].to_numpy()

    async def callback(
        done: bool,
        params: npt.NDArray[np.float64],
        simulation: npt.NDArray[np.float64],
        results: dict[str, float],
    ) -> None:
        await send(
            ws,
            "result",
            {
                "done": done,
                "simulation": _data.select("date").with_columns(
                    pl.Series("streamflow", simulation)
                ),
                "params": params,
                "objective": results[msg_data["objective"]],
            },
        )

    await calibration.calibrate(
        precipitation,
        temperature,
        pet,
        observations,
        day_of_year,
        elevation_layers,
        median_elevation,
        metadata["qnbv"],
        msg_data["hydroModel"],
        msg_data["snowModel"],
        msg_data["objective"],
        msg_data["transformation"],
        msg_data["algorithm"],
        msg_data["algorithmParams"],
        callback=callback,
        stop_event=stop_event,
    )
