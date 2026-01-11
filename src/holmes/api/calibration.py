import asyncio
from typing import Any, get_args

import numpy as np
import numpy.typing as npt
import polars as pl
from starlette.routing import BaseRoute, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from holmes import data
from holmes.logging import logger
from holmes.models import calibration, evaluate, hydro, snow
from holmes.utils.print import format_list

from .utils import convert_for_json

##########
# public #
##########


def get_routes() -> list[BaseRoute]:
    return [
        WebSocketRoute("/", endpoint=_websocket_handler),
    ]


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
        case "ping":
            pass
        case "config":
            await _handle_config_message(ws)
        case "observations":
            await _handle_observations_message(ws, msg.get("data", {}))
        case "manual":
            await _handle_manual_calibration_message(ws, msg.get("data", {}))
        case "calibration_start":
            stop_event = asyncio.Event()
            setattr(ws.state, "stop_event", stop_event)
            asyncio.create_task(
                _handle_calibration_start_message(
                    ws, msg.get("data", {}), stop_event
                )
            )
        case "calibration_stop":
            if hasattr(ws.state, "stop_event"):
                getattr(ws.state, "stop_event").set()
        case _:
            await _send(ws, "error", f"Unknown message type {msg['type']}.")


async def _handle_config_message(ws: WebSocket) -> None:
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
    await _send(ws, "config", config)


async def _handle_observations_message(
    ws: WebSocket, msg_data: dict[str, Any]
) -> None:
    if any(key not in msg_data for key in ("catchment", "start", "end")):
        await _send(
            ws,
            "error",
            "`catchment`, `start` and `end` must be provided.",
        )
        return

    _data = data.read_data(
        msg_data["catchment"], msg_data["start"], msg_data["end"]
    )

    await _send(ws, "observations", _data.select("date", "streamflow"))


async def _handle_manual_calibration_message(
    ws: WebSocket, msg_data: dict[str, Any]
) -> None:
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
        await _send(
            ws,
            "error",
            format_list(needed_keys, surround="`") + " must be provided.",
        )
        return

    _data = data.read_data(
        msg_data["catchment"], msg_data["start"], msg_data["end"]
    )
    metadata = data.read_cemaneige_info(msg_data["catchment"])

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

    await _send(
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
        await _send(
            ws,
            "error",
            format_list(needed_keys, surround="`") + " must be provided.",
        )
        return

    _data = data.read_data(
        msg_data["catchment"], msg_data["start"], msg_data["end"]
    )
    metadata = data.read_cemaneige_info(msg_data["catchment"])

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
        await _send(
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


###########
# private #
###########


async def _send(ws: WebSocket, event: str, data: Any) -> None:
    await ws.send_json({"type": event, "data": convert_for_json(data)})
