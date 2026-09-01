import asyncio
import math
import threading
import time
from datetime import date
from typing import Any, cast, get_args

import numpy as np
import polars as pl
from starlette.websockets import WebSocket

import holmes.data.hydro
import holmes.data.joined
import holmes.model
from holmes.data.weather import WeatherMethod, max_n_stations, min_n_stations
from holmes.model import (
    Algorithm,
    HydroModel,
    Objective,
    SnowModel,
    Transformation,
)
from holmes.model_info import get_calibration_info
from holmes.api.utils import send
from holmes.utils.print import done_print, fail_print, warn_print

#########
# state #
#########

# the prebuilt station/streamflow/weather join is read from disk once per
# weather method; the read is cheap IPC but not free, so it is memoised and
# guarded by a lock to avoid two concurrent requests both paying for it.
_data_cache: dict[str, pl.DataFrame] = {}
_data_lock = asyncio.Lock()

##########
# public #
##########


async def handle_calibration_message(
    ws: WebSocket, msg: dict[str, Any]
) -> None:
    match msg.get("type"):
        case "calibration_info":
            await _handle_info(ws)
        case "calibration_data":
            await _handle_data(ws, msg)
        case "calibration_manual":
            await _handle_manual(ws, msg)
        case "calibration_start":
            await _handle_start(ws, msg)
        case "calibration_stop":
            await _handle_stop(ws, msg)


def cleanup_calibration(ws: WebSocket) -> None:
    # Cancelling an `asyncio.to_thread` task does not stop its worker thread;
    # setting the stop events is what actually terminates the running SCE loops.
    stops = getattr(ws.state, "calibration_stops", None)
    if stops:
        for event in stops.values():
            event.set()


# the data/serialisation helpers below are public because simulation
# shares them (and, through get_data, the memoised join)


async def get_data(method: WeatherMethod, n_stations: int) -> pl.DataFrame:
    # the station count only changes the nearest-stations product, but keying
    # on it unconditionally is harmless: the other methods always arrive with
    # the same default
    key = f"{method}|{n_stations}"
    async with _data_lock:
        if key not in _data_cache:
            # a sync IPC read of the prebuilt joined product, kept off the
            # event loop
            _data_cache[key] = await asyncio.to_thread(
                holmes.data.joined.read_joined_data,
                method=method,
                n_stations=n_stations,
            )
        return _data_cache[key]


def filter_data(
    data: pl.DataFrame, station: str, start: str, end: str
) -> pl.DataFrame:
    # config stores station ids, so filter on `id` (never the friendly name)
    return data.filter(
        (pl.col("id") == station)
        & pl.col("datetime").is_between(
            date.fromisoformat(start), date.fromisoformat(end)
        )
    ).sort("datetime")


def filter_data_with_warmup(
    data: pl.DataFrame,
    station: str,
    start: str,
    end: str,
    warmup_years: int,
) -> tuple[pl.DataFrame, int]:
    # the warmup lead is PREPENDED before [start, end] rather than taken from
    # inside it, so the whole chosen period is scored. it clamps to whatever
    # rows exist before `start` (the weather record begins in 1940), which is
    # why the step count is the actual lead height and not `365 * years`
    start_date = date.fromisoformat(start)
    lead_start = holmes.model.warmup_start(start_date, warmup_years)
    filtered = filter_data(data, station, lead_start.isoformat(), end)
    warmup_steps = int((filtered["datetime"] < start_date).sum())
    return filtered, warmup_steps


def sanitize(values: Any) -> list[float | None]:
    # convert_for_json only nulls non-finite values inside DataFrames; a bare
    # inf/nan in a list breaks the client's JSON.parse, so every params and
    # simulation array crossing the wire is sanitised here
    result: list[float | None] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            result.append(None)
            continue
        result.append(number if math.isfinite(number) else None)
    return result


def sanitize_objectives(
    objectives: dict[str, Any],
) -> dict[str, float | None]:
    return {name: sanitize([value])[0] for name, value in objectives.items()}


###########
# private #
###########


async def _handle_info(ws: WebSocket) -> None:
    # descriptions and bounds are static and instant, so no task tracking
    await send(ws, "calibration_info", get_calibration_info())


async def _handle_data(ws: WebSocket, msg: dict[str, Any]) -> None:
    station = msg.get("station")
    method = msg.get("method")
    start = msg.get("start")
    end = msg.get("end")
    # absent on messages from a tab predating the field, so it defaults
    n_stations = _coerce_n_stations(msg.get("n_stations", 3))
    warmup_years = _coerce_int(msg.get("warmupYears", 0))

    if station not in holmes.data.hydro.STATIONS:
        await send(ws, "error", f"Unknown station {station}.")
        return
    if method not in get_args(WeatherMethod):
        await send(ws, "error", f"Unknown weather method {method}.")
        return
    if not _valid_dates(start, end):
        await send(ws, "error", "Invalid calibration date range.")
        return
    if n_stations is None:
        await send(ws, "error", "Invalid number of nearest stations.")
        return
    if warmup_years is None or warmup_years < 0:
        await send(ws, "error", "Invalid number of warmup years.")
        return

    # a new pick supersedes any pending load (data assembly can be slow)
    previous = getattr(ws.state, "calibration_data_task", None)
    if previous is not None and not previous.done():
        previous.cancel()

    task = asyncio.create_task(
        _load_data(
            ws,
            cast(str, station),
            cast(str, start),
            cast(str, end),
            cast(WeatherMethod, method),
            n_stations,
            warmup_years,
        )
    )
    ws.state.calibration_data_task = task
    if not hasattr(ws.state, "tasks"):
        ws.state.tasks = set()
    ws.state.tasks.add(task)
    task.add_done_callback(ws.state.tasks.discard)


async def _load_data(
    ws: WebSocket,
    station: str,
    start: str,
    end: str,
    method: WeatherMethod,
    n_stations: int,
    warmup_years: int,
) -> None:
    try:
        data = await get_data(method, n_stations)
        filtered, warmup_steps = filter_data_with_warmup(
            data, station, start, end, warmup_years
        )
        # the calibration-window qnbv, matching what `calibrate_stream`
        # computes internally; the lead is spin-up only
        qnbv = holmes.model.calculate_qnbv(filtered.slice(warmup_steps))
    except Exception as exc:
        await _send_error(
            ws, message=f"Failed to load calibration data: {exc}"
        )
        return

    # every field is echoed verbatim so the client can key its cache and match
    # a reply to the request that produced it
    await send(
        ws,
        "calibration_data",
        {
            "station": station,
            "start": start,
            "end": end,
            "method": method,
            "n_stations": n_stations,
            "warmupYears": warmup_years,
            "qnbv": sanitize([qnbv])[0],
            "data": filtered.select("datetime", "streamflow"),
        },
    )


async def _handle_manual(ws: WebSocket, msg: dict[str, Any]) -> None:
    station = msg.get("station")
    method = msg.get("method")
    start = msg.get("start")
    end = msg.get("end")
    hydro_model = msg.get("hydroModel")
    transformation = msg.get("transformation")
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
        await send(ws, "error", "Invalid calibration date range.")
        return
    if n_stations is None:
        await send(ws, "error", "Invalid number of nearest stations.")
        return
    if hydro_model not in get_args(HydroModel):
        await send(ws, "error", f"Unknown hydro model {hydro_model}.")
        return
    snow_ok, snow_model = _parse_snow(msg.get("snowModel"))
    if not snow_ok:
        await send(ws, "error", f"Unknown snow model {msg.get('snowModel')}.")
        return
    if transformation not in get_args(Transformation):
        await send(ws, "error", f"Unknown transformation {transformation}.")
        return
    if warmup_years is None or warmup_years < 0 or request_id is None:
        await send(ws, "error", "Invalid numeric calibration field.")
        return
    hydro_params = _coerce_floats(msg.get("hydroParams"))
    if hydro_params is None:
        await send(ws, "error", "Invalid hydro parameters.")
        return

    # one manual request per model: a new pick for the same model supersedes
    # the in-flight one, but different models run independently
    if not hasattr(ws.state, "manual_tasks"):
        ws.state.manual_tasks = {}
    previous = ws.state.manual_tasks.get(hydro_model)
    if previous is not None and not previous.done():
        previous.cancel()

    task = asyncio.create_task(
        _run_manual(
            ws,
            cast(str, station),
            cast(str, start),
            cast(str, end),
            cast(WeatherMethod, method),
            n_stations,
            cast(HydroModel, hydro_model),
            snow_model,
            cast(Transformation, transformation),
            warmup_years,
            hydro_params,
            request_id,
        )
    )
    ws.state.manual_tasks[hydro_model] = task
    if not hasattr(ws.state, "tasks"):
        ws.state.tasks = set()
    ws.state.tasks.add(task)
    task.add_done_callback(ws.state.tasks.discard)


async def _run_manual(
    ws: WebSocket,
    station: str,
    start: str,
    end: str,
    method: WeatherMethod,
    n_stations: int,
    hydro_model: HydroModel,
    snow_model: SnowModel | None,
    transformation: Transformation,
    warmup_years: int,
    hydro_params: list[float],
    request_id: int,
) -> None:
    try:
        data = await get_data(method, n_stations)
        filtered, warmup_steps = filter_data_with_warmup(
            data, station, start, end, warmup_years
        )
        _check_observations(filtered, warmup_steps)
        simulation, objectives = await asyncio.to_thread(
            holmes.model.simulate_manual,
            filtered,
            hydro_model,
            snow_model,
            transformation,
            warmup_steps,
            hydro_params=np.array(hydro_params, dtype=np.float64),
        )
    except Exception as exc:
        await _send_error(
            ws,
            hydro_model=hydro_model,
            request_id=request_id,
            message=str(exc),
        )
        return

    await send(
        ws,
        "calibration_result",
        {
            "hydroModel": hydro_model,
            "requestId": request_id,
            "params": sanitize(hydro_params),
            "objectives": sanitize_objectives(objectives),
            "simulation": sanitize(simulation),
        },
    )


async def _handle_start(ws: WebSocket, msg: dict[str, Any]) -> None:
    station = msg.get("station")
    method = msg.get("method")
    start = msg.get("start")
    end = msg.get("end")
    hydro_models = msg.get("hydroModels")
    objective = msg.get("objective")
    transformation = msg.get("transformation")
    algorithm = msg.get("algorithm")
    run_id = _coerce_int(msg.get("runId"))
    warmup_years = _coerce_int(msg.get("warmupYears"))
    n_stations = _coerce_n_stations(msg.get("n_stations", 3))

    if station not in holmes.data.hydro.STATIONS:
        await send(ws, "error", f"Unknown station {station}.")
        return
    if method not in get_args(WeatherMethod):
        await send(ws, "error", f"Unknown weather method {method}.")
        return
    if not _valid_dates(start, end):
        await send(ws, "error", "Invalid calibration date range.")
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
    if objective not in get_args(Objective):
        await send(ws, "error", f"Unknown objective {objective}.")
        return
    if transformation not in get_args(Transformation):
        await send(ws, "error", f"Unknown transformation {transformation}.")
        return
    if algorithm not in get_args(Algorithm):
        await send(ws, "error", f"Unknown algorithm {algorithm}.")
        return
    if warmup_years is None or warmup_years < 0 or run_id is None:
        await send(ws, "error", "Invalid numeric calibration field.")
        return
    algorithm_params = _coerce_algorithm_params(msg.get("algorithmParams"))
    if algorithm_params is None:
        await send(ws, "error", "Invalid algorithm parameters.")
        return

    # a new run first stops every model still running from a previous run, then
    # installs a fresh stop event per model so per-model stops stay independent
    for event in getattr(ws.state, "calibration_stops", {}).values():
        event.set()
    stops = {model: threading.Event() for model in hydro_models}
    ws.state.calibration_stops = stops
    if not hasattr(ws.state, "tasks"):
        ws.state.tasks = set()

    for model in hydro_models:
        task = asyncio.create_task(
            _run_model_calibration(
                ws,
                cast(str, station),
                cast(str, start),
                cast(str, end),
                cast(WeatherMethod, method),
                n_stations,
                cast(HydroModel, model),
                snow_model,
                cast(Objective, objective),
                cast(Transformation, transformation),
                warmup_years,
                cast(Algorithm, algorithm),
                algorithm_params,
                run_id,
                stops[model],
            )
        )
        ws.state.tasks.add(task)
        task.add_done_callback(ws.state.tasks.discard)


async def _run_model_calibration(
    ws: WebSocket,
    station: str,
    start: str,
    end: str,
    method: WeatherMethod,
    n_stations: int,
    hydro_model: HydroModel,
    snow_model: SnowModel | None,
    objective: Objective,
    transformation: Transformation,
    warmup_years: int,
    algorithm: Algorithm,
    algorithm_params: dict[str, Any],
    run_id: int,
    stop_event: threading.Event,
) -> None:
    # captured before to_thread: the callback runs in the worker thread and
    # needs the loop to schedule sends back onto it
    loop = asyncio.get_running_loop()

    try:
        data = await get_data(method, n_stations)
        filtered, warmup_steps = filter_data_with_warmup(
            data, station, start, end, warmup_years
        )
        _check_observations(filtered, warmup_steps)
    except Exception as exc:
        await _send_error(
            ws, hydro_model=hydro_model, run_id=run_id, message=str(exc)
        )
        return

    # closure state so the callback can throttle simulation frames and the
    # runner can synthesise a final stopped frame from the last step seen
    last_sim_time = 0.0
    last: dict[str, Any] = {
        "step": 0,
        "params": None,
        "objectives": None,
        "simulation": None,
        "done_sent": False,
    }

    def callback(
        step_i: int,
        done: bool,
        params: Any,
        simulation: Any,
        objectives: Any,
    ) -> None:
        nonlocal last_sim_time
        now = time.monotonic()
        # simulation is heavy: send it at most twice a second per model, but
        # always on the final frame
        include_sim = done or (now - last_sim_time >= 0.5)

        params_ = sanitize(params)
        objectives_ = sanitize_objectives(
            {
                "rmse": objectives[0],
                "nse": objectives[1],
                "kge": objectives[2],
            }
        )
        simulation_ = sanitize(simulation)

        last["step"] = step_i
        last["params"] = params_
        last["objectives"] = objectives_
        last["simulation"] = simulation_
        if include_sim:
            last_sim_time = now
        if done:
            last["done_sent"] = True

        frame = {
            "hydroModel": hydro_model,
            "runId": run_id,
            "step": step_i,
            "done": done,
            "stopped": False,
            "params": params_,
            "objectives": objectives_,
            "simulation": simulation_ if include_sim else None,
        }
        # block the worker until the send completes: gives ordering and
        # backpressure so a fast SCE loop cannot flood the socket
        future = asyncio.run_coroutine_threadsafe(
            send(ws, "calibration_step", frame, quiet=True), loop
        )
        future.result(timeout=10)

    done_print(f"Calibrating {hydro_model}...")
    started = time.monotonic()
    try:
        await asyncio.to_thread(
            holmes.model.calibrate_stream,
            filtered,
            hydro_model,
            objective,
            snow_model,
            transformation,
            warmup_steps,
            algorithm=algorithm,
            params=algorithm_params,
            callback=callback,
            stop_event=stop_event,
        )
    except Exception as exc:
        await _send_error(
            ws, hydro_model=hydro_model, run_id=run_id, message=str(exc)
        )
        return

    elapsed = time.monotonic() - started
    if stop_event.is_set():
        warn_print(f"Stopped calibrating {hydro_model} after {elapsed:.1f}s.")
    else:
        done_print(f"Calibrated {hydro_model} in {elapsed:.1f}s.")

    # calibrate_stream does not re-invoke the callback after a stop-break, so if
    # the run ended on a stop the final done/stopped frame is emitted here from
    # the last captured step
    if (
        stop_event.is_set()
        and not last["done_sent"]
        and last["params"] is not None
    ):
        await send(
            ws,
            "calibration_step",
            {
                "hydroModel": hydro_model,
                "runId": run_id,
                "step": last["step"],
                "done": True,
                "stopped": True,
                "params": last["params"],
                "objectives": last["objectives"],
                "simulation": last["simulation"],
            },
        )


async def _handle_stop(ws: WebSocket, msg: dict[str, Any]) -> None:
    stops = getattr(ws.state, "calibration_stops", None)
    if not stops:
        return
    model = msg.get("hydroModel")
    if model is None:
        for event in stops.values():
            event.set()
    else:
        event = stops.get(model)
        if event is not None:
            event.set()


def _check_observations(filtered: pl.DataFrame, warmup_steps: int = 0) -> None:
    # the data join keeps weather days without observations (for simulating
    # unobserved periods); calibrating on them would grind the optimizer on
    # ±inf objectives and return meaningless parameters. checked on the scored
    # window only: the warmup lead may legitimately predate the record
    if filtered["streamflow"].slice(warmup_steps).is_not_null().sum() == 0:
        raise ValueError(
            "No streamflow observations in the calibration period."
        )


def _valid_dates(start: Any, end: Any) -> bool:
    try:
        date.fromisoformat(start)
        date.fromisoformat(end)
    except (TypeError, ValueError):
        return False
    return True


def _parse_snow(raw: Any) -> tuple[bool, SnowModel | None]:
    match raw:
        case "none":
            return True, None
        case "cemaneige":
            return True, "cemaneige"
        case _:
            return False, None


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_n_stations(value: Any) -> int | None:
    n_stations = _coerce_int(value)
    if (
        n_stations is None
        or not min_n_stations <= n_stations <= max_n_stations
    ):
        return None
    return n_stations


def _coerce_floats(values: Any) -> list[float] | None:
    if not isinstance(values, list):
        return None
    try:
        return [float(value) for value in values]
    except (TypeError, ValueError):
        return None


def _coerce_algorithm_params(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        return None
    params: dict[str, Any] = {}
    for spec in holmes.model.get_config("sce"):
        name = cast(str, spec["name"])
        value = raw.get(name, spec["default"])
        try:
            params[name] = int(value) if spec["integer"] else float(value)
        except (TypeError, ValueError):
            return None
    return params


async def _send_error(
    ws: WebSocket,
    *,
    hydro_model: str | None = None,
    run_id: int | None = None,
    request_id: int | None = None,
    message: str,
) -> None:
    fail_print(message)
    await send(
        ws,
        "calibration_error",
        {
            "hydroModel": hydro_model,
            "runId": run_id,
            "requestId": request_id,
            "message": message,
        },
    )
