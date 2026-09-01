import asyncio
import time
import warnings
from typing import Any, cast, get_args

import numpy as np
import numpy.typing as npt
from starlette.websockets import WebSocket

import holmes.data.hydro
import holmes.model

# the coercers are calibration privates by convention, but shared here so
# the two websocket APIs validate their common fields identically
from holmes.api.calibration import (
    _coerce_floats,
    _coerce_int,
    _coerce_n_stations,
    _parse_snow,
    _valid_dates,
    filter_data_with_warmup,
    get_data,
    sanitize,
    sanitize_objectives,
)
from holmes.data.weather import WeatherMethod
from holmes.model import HydroModel, SnowModel
from holmes.api.utils import send
from holmes.utils.print import done_print, fail_print

##########
# public #
##########


async def handle_simulation_message(
    ws: WebSocket, msg: dict[str, Any]
) -> None:
    match msg.get("type"):
        case "simulation_data":
            await _handle_data(ws, msg)


###########
# private #
###########


async def _handle_data(ws: WebSocket, msg: dict[str, Any]) -> None:
    station = msg.get("station")
    method = msg.get("method")
    start = msg.get("start")
    end = msg.get("end")
    hydro_models = msg.get("hydroModels")
    request_id = _coerce_int(msg.get("requestId"))
    warmup_years = _coerce_int(msg.get("warmupYears"))
    n_stations = _coerce_n_stations(msg.get("n_stations", 3))

    if station not in holmes.data.hydro.STATIONS:
        await send(ws, "error", f"Unknown station {station}.")
        return
    if method not in get_args(WeatherMethod):
        await send(ws, "error", f"Unknown weather method {method}.")
        return
    if not _valid_dates(start, end):
        await send(ws, "error", "Invalid simulation date range.")
        return
    if n_stations is None:
        await send(ws, "error", "Invalid number of nearest stations.")
        return
    if (
        not isinstance(hydro_models, list)
        or not hydro_models
        or any(model not in get_args(HydroModel) for model in hydro_models)
    ):
        await send(ws, "error", f"Unknown hydro model in {hydro_models}.")
        return
    snow_ok, snow_model = _parse_snow(msg.get("snowModel"))
    if not snow_ok:
        await send(ws, "error", f"Unknown snow model {msg.get('snowModel')}.")
        return
    if warmup_years is None or warmup_years < 0 or request_id is None:
        await send(ws, "error", "Invalid numeric simulation field.")
        return
    raw_params = msg.get("hydroParams")
    if not isinstance(raw_params, dict):
        await send(ws, "error", "Invalid hydro parameters.")
        return
    hydro_params: dict[str, list[float]] = {}
    for model in hydro_models:
        params = _coerce_floats(raw_params.get(model))
        if params is None:
            await send(ws, "error", f"Invalid hydro parameters for {model}.")
            return
        hydro_params[model] = params
    # the calibrated snow parameters (incl. qnbv) are carried onto the
    # simulation window rather than recomputed, mirroring run_experiment
    snow_params = None
    if snow_model is not None:
        snow_params = _coerce_floats(msg.get("snowParams"))
        if snow_params is None:
            await send(ws, "error", "Invalid snow parameters.")
            return

    # one reply covers every model, so a new request supersedes a pending one
    previous = getattr(ws.state, "simulation_task", None)
    if previous is not None and not previous.done():
        previous.cancel()

    task = asyncio.create_task(
        _load_simulation(
            ws,
            cast(str, station),
            cast(str, start),
            cast(str, end),
            cast(WeatherMethod, method),
            n_stations,
            cast(list[HydroModel], hydro_models),
            snow_model,
            hydro_params,
            snow_params,
            warmup_years,
            request_id,
        )
    )
    ws.state.simulation_task = task
    if not hasattr(ws.state, "tasks"):
        ws.state.tasks = set()
    ws.state.tasks.add(task)
    task.add_done_callback(ws.state.tasks.discard)


async def _load_simulation(
    ws: WebSocket,
    station: str,
    start: str,
    end: str,
    method: WeatherMethod,
    n_stations: int,
    hydro_models: list[HydroModel],
    snow_model: SnowModel | None,
    hydro_params: dict[str, list[float]],
    snow_params: list[float] | None,
    warmup_years: int,
    request_id: int,
) -> None:
    snow = (
        np.array(snow_params, dtype=np.float64)
        if snow_params is not None
        else None
    )
    started = time.monotonic()
    try:
        data = await get_data(method, n_stations)
        filtered, warmup_steps = filter_data_with_warmup(
            data, station, start, end, warmup_years
        )
        # an empty window (a period outside the station's record) would only
        # fail later as an obscure dtype error inside the models; the scored
        # window is what must be non-empty, the warmup lead may well be
        if filtered.height - warmup_steps == 0:
            await _send_error(
                ws,
                request_id=request_id,
                message=(
                    f"No data for station {station} between {start} and {end}."
                ),
            )
            return
        results: dict[str, dict[str, Any]] = {}
        simulations: list[npt.NDArray[np.float64]] = []
        for model in hydro_models:
            simulation, metrics = await asyncio.to_thread(
                holmes.model.simulate_with_metrics,
                filtered,
                model,
                snow_model,
                warmup_steps,
                hydro_params=np.array(hydro_params[model], dtype=np.float64),
                snow_params=snow,
            )
            simulations.append(simulation)
            results[model] = {
                "simulation": sanitize(simulation),
                "metrics": sanitize_objectives(metrics),
            }
        median, median_metrics = await asyncio.to_thread(
            _evaluate_median,
            filtered["streamflow"].to_numpy(),
            simulations,
            warmup_steps,
        )
    except Exception as exc:
        await _send_error(
            ws,
            request_id=request_id,
            message=f"Failed to run simulation: {exc}",
        )
        return

    elapsed = time.monotonic() - started
    done_print(
        f"Simulated {station} ({', '.join(hydro_models)}) in {elapsed:.1f}s."
    )

    # every request field is echoed so the client can match the reply to the
    # request that produced it
    await send(
        ws,
        "simulation_result",
        {
            "station": station,
            "start": start,
            "end": end,
            "method": method,
            "n_stations": n_stations,
            "warmupYears": warmup_years,
            "requestId": request_id,
            "data": filtered.select("datetime", "streamflow"),
            "results": results,
            "median": {
                "simulation": sanitize(median),
                "metrics": sanitize_objectives(median_metrics),
            },
        },
    )


def _evaluate_median(
    observations: npt.NDArray[np.float64],
    simulations: list[npt.NDArray[np.float64]],
    warmup_steps: int,
) -> tuple[npt.NDArray[np.float64], dict[str, float]]:
    # the ensemble answer is the pointwise median of the member simulations,
    # scored like any member; a step with no finite member yields NaN, which
    # nanmedian reports with a RuntimeWarning that is expected and silenced
    stack = np.stack(simulations)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median = np.nanmedian(
            np.where(np.isfinite(stack), stack, np.nan), axis=0
        )
    metrics = holmes.model.evaluate_simulation_metrics(
        observations, median, warmup_steps
    )
    return median, metrics


async def _send_error(
    ws: WebSocket, *, request_id: int | None = None, message: str
) -> None:
    fail_print(message)
    await send(
        ws,
        "simulation_error",
        {"requestId": request_id, "message": message},
    )
