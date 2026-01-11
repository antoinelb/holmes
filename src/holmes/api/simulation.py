from typing import Any, cast

import numpy as np
import numpy.typing as npt
import polars as pl
from starlette.routing import BaseRoute, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from holmes import data
from holmes.logging import logger
from holmes.models import hydro, snow
from holmes.models.utils import evaluate
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
        case "ping":
            pass
        case "config":
            if "data" not in msg:
                await send(ws, "error", "The catchment must be provided.")
            await _handle_config_message(ws, msg["data"])
        case "observations":
            await _handle_observations_message(ws, msg.get("data", {}))
        case "simulation":
            await _handle_simulation_message(ws, msg.get("data", {}))
        case _:
            await send(ws, "error", f"Unknown message type {msg['type']}.")


async def _handle_config_message(ws: WebSocket, msg_data: str) -> None:
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

    _data = data.read_data(
        msg_data["catchment"], msg_data["start"], msg_data["end"]
    )

    await send(ws, "observations", _data.select("date", "streamflow"))


async def _handle_simulation_message(
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

    _data = data.read_data(catchment, start, end)
    metadata = data.read_cemaneige_info(catchment)

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
    qnbv = metadata["qnbv"]

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
        results.append(
            {
                "name": "multimodel",
                "nse_none": evaluate(observations, streamflow, "nse", "none"),
                "nse_sqrt": evaluate(observations, streamflow, "nse", "sqrt"),
                "nse_log": evaluate(observations, streamflow, "nse", "log"),
                "mean_bias": evaluate(
                    observations, streamflow, "mean_bias", "none"
                ),
                "deviation_bias": evaluate(
                    observations, streamflow, "deviation_bias", "none"
                ),
                "correlation": evaluate(
                    observations, streamflow, "correlation", "none"
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
    temperature: npt.NDArray[np.float64],
    pet: npt.NDArray[np.float64],
    day_of_year: npt.NDArray[np.uintp],
    elevation_layers: npt.NDArray[np.float64],
    median_elevation: float,
    qnbv: float,
    observations: npt.NDArray[np.float64],
    hydro_model: str,
    snow_model: str | None,
    hydro_params: dict[str, float],
) -> tuple[npt.NDArray[np.float64], dict[str, float]]:

    hydro_simulate = hydro.get_model(cast(hydro.HydroModel, hydro_model))
    hydro_params_ = np.array(list(hydro_params.values()))

    if snow_model is not None:
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

    results = {
        "nse_none": evaluate(observations, streamflow, "nse", "none"),
        "nse_sqrt": evaluate(observations, streamflow, "nse", "sqrt"),
        "nse_log": evaluate(observations, streamflow, "nse", "log"),
        "mean_bias": evaluate(observations, streamflow, "mean_bias", "none"),
        "deviation_bias": evaluate(
            observations, streamflow, "deviation_bias", "none"
        ),
        "correlation": evaluate(
            observations, streamflow, "correlation", "none"
        ),
    }

    return streamflow, results
