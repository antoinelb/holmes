import asyncio
import time
import warnings
from datetime import date
from typing import Any, cast, get_args

import numpy as np
import numpy.typing as npt
import polars as pl
from starlette.websockets import WebSocket

import holmes.data.hydro
import holmes.data.projection
import holmes.model

# the coercers are calibration privates by convention, but shared here so
# the websocket APIs validate their common fields identically
from holmes.api.calibration import (
    _coerce_floats,
    _coerce_int,
    _coerce_n_stations,
    _parse_snow,
    _valid_dates,
    filter_data_with_warmup,
    get_data,
    sanitize,
)
from holmes.data.weather import WeatherMethod
from holmes.model import HydroModel, SnowModel
from holmes.api.utils import send
from holmes.utils.print import done_print, fail_print

#########
# state #
#########

# the per-station product is ~2.8M rows; the read is cheap ipc but not free,
# so it is memoised like calibration._data_cache
_projection_cache: dict[str, pl.DataFrame] = {}
_projection_lock = asyncio.Lock()

# full-window member simulations per (station, climate model, scenario,
# hydro model, parameters): simulating is ~2/3 of a request, and a horizon
# switch changes none of the inputs, so cached sims make it re-aggregate only.
# written from the to_thread worker without a lock — dict ops are atomic and
# a lost race merely recomputes a cache entry
_simulation_cache: dict[
    tuple[Any, ...], dict[str, npt.NDArray[np.float64]]
] = {}
# ~12 MB per entry (50 members x 80 noleap years of float64); FIFO eviction
max_cached_ensembles = 8

horizons: dict[str, tuple[int, int]] = {
    "2020-2049": (2020, 2049),
    "2040-2069": (2040, 2069),
    "2070-2099": (2070, 2099),
}
# a year shorter than this is a record edge whose seasonal extremes would be
# computed from a handful of days; 360 rather than 365 keeps noleap 2099,
# which only misses Dec 31
min_year_days = 360

##########
# public #
##########


async def handle_projection_message(
    ws: WebSocket, msg: dict[str, Any]
) -> None:
    match msg.get("type"):
        case "projection_data":
            await _handle_data(ws, msg)


###########
# private #
###########


async def _handle_data(ws: WebSocket, msg: dict[str, Any]) -> None:
    station = msg.get("station")
    start = msg.get("start")
    end = msg.get("end")
    method = msg.get("method")
    hydro_models = msg.get("hydroModels")
    climate_model = msg.get("climateModel")
    scenario = msg.get("scenario")
    horizon = msg.get("horizon")
    request_id = _coerce_int(msg.get("requestId"))
    warmup_years = _coerce_int(msg.get("warmupYears"))
    n_stations = _coerce_n_stations(msg.get("n_stations", 3))

    if station not in holmes.data.hydro.STATIONS:
        await send(ws, "error", f"Unknown station {station}.")
        return
    if method not in get_args(WeatherMethod):
        await send(ws, "error", f"Unknown weather method {method}.")
        return
    # the simulation period anchors the historical reference
    if not _valid_dates(start, end):
        await send(ws, "error", "Invalid simulation period.")
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
    # the climate model / scenario pairing is data, not code: the product's
    # `ensemble` column carries the dataset labels ("ClimEx", "ESPO-G6-R2"),
    # and an unknown pair falls out through the empty-filter guard below
    if not isinstance(climate_model, str) or not climate_model:
        await send(ws, "error", f"Invalid climate model {climate_model}.")
        return
    if not isinstance(scenario, str) or not scenario:
        await send(ws, "error", f"Invalid scenario {scenario}.")
        return
    if horizon not in horizons:
        await send(ws, "error", f"Unknown horizon {horizon}.")
        return
    if request_id is None or warmup_years is None or warmup_years < 0:
        await send(ws, "error", "Invalid numeric projection field.")
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
    # projection window rather than recomputed, mirroring run_experiment
    snow_params = None
    if snow_model is not None:
        snow_params = _coerce_floats(msg.get("snowParams"))
        if snow_params is None:
            await send(ws, "error", "Invalid snow parameters.")
            return

    # one reply covers every model and member, so a new request supersedes a
    # pending one
    previous = getattr(ws.state, "projection_task", None)
    if previous is not None and not previous.done():
        previous.cancel()

    task = asyncio.create_task(
        _load_projection(
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
            cast(str, climate_model),
            cast(str, scenario),
            cast(str, horizon),
            warmup_years,
            request_id,
        )
    )
    ws.state.projection_task = task
    if not hasattr(ws.state, "tasks"):
        ws.state.tasks = set()
    ws.state.tasks.add(task)
    task.add_done_callback(ws.state.tasks.discard)


async def _load_projection(
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
    climate_model: str,
    scenario: str,
    horizon: str,
    warmup_years: int,
    request_id: int,
) -> None:
    snow = (
        np.array(snow_params, dtype=np.float64)
        if snow_params is not None
        else None
    )
    try:
        stations = (
            await asyncio.to_thread(holmes.data.hydro.get_station_data)
        ).filter(pl.col("id") == station)
        # the server never builds data; refuse with a pointer to the build
        # path rather than raising on the read below
        if not holmes.data.projection.has_projection_data(stations):
            await _send_error(
                ws,
                request_id=request_id,
                message=(
                    f"Projection data for station {station} is not"
                    " downloaded yet — run `holmes download`."
                ),
            )
            return
        product = await _get_projection_data(station, stations)
        member_counts = {
            row["scenario"]: row["n"]
            for row in product.group_by("scenario")
            .agg(pl.col("member").n_unique().alias("n"))
            .to_dicts()
        }
        # the full 2020-2099 window is always simulated (and cached), so a
        # horizon switch changes only the aggregation range
        filtered = product.filter(
            (pl.col("ensemble") == climate_model)
            & (pl.col("scenario") == scenario)
        ).join(stations.select("id", "lat", "elevation_layers"), on="id")
        if filtered.height == 0:
            await _send_error(
                ws,
                request_id=request_id,
                message=(
                    f"No projection data for station {station}, climate"
                    f" model {climate_model} and scenario {scenario}."
                ),
            )
            return
        start_year, end_year = horizons[horizon]
        # the warmup is the simulation step's, so the two benches agree; it
        # only binds for the first horizon, whose start coincides with the
        # product start (later horizons get >= 20 years of natural spin-up)
        agg_start_year = max(
            start_year,
            holmes.data.projection.projection_start_year + warmup_years,
        )

        done_print(
            f"Running projection for {station} ({climate_model}, "
            f"{scenario}, {len(hydro_models)} hydro models)..."
        )
        started = time.monotonic()
        results, median = await asyncio.to_thread(
            _run_ensemble,
            filtered,
            hydro_models,
            snow_model,
            hydro_params,
            snow,
            agg_start_year,
            end_year,
            (station, climate_model, scenario),
        )
        # the reference runs over the simulation period, extended backwards
        # so the models spin up before the period rather than inside it
        # (_run_historical excludes the lead from the aggregation by exact
        # date); same convention as the calibration and simulation steps
        observed, _ = filter_data_with_warmup(
            await get_data(method, n_stations),
            station,
            start,
            end,
            warmup_years,
        )
        historical = await asyncio.to_thread(
            _run_historical,
            observed,
            hydro_models,
            snow_model,
            hydro_params,
            snow,
            date.fromisoformat(start),
            date.fromisoformat(end),
        )
        elapsed = time.monotonic() - started
        done_print(
            f"Ran projection for {station} ({climate_model}, {scenario}) "
            f"in {elapsed:.1f}s."
        )
    except Exception as exc:
        await _send_error(
            ws,
            request_id=request_id,
            message=f"Failed to run projection: {exc}",
        )
        return

    # every request field is echoed so the client can match the reply to the
    # request that produced it
    await send(
        ws,
        "projection_result",
        {
            "station": station,
            "start": start,
            "end": end,
            "method": method,
            "n_stations": n_stations,
            "hydroModels": hydro_models,
            "snowModel": snow_model if snow_model is not None else "none",
            "climateModel": climate_model,
            "scenario": scenario,
            "horizon": horizon,
            "warmupYears": warmup_years,
            "requestId": request_id,
            "memberCounts": member_counts,
            "results": results,
            "median": median,
            "historical": historical,
        },
    )


async def _get_projection_data(
    station: str, stations: pl.DataFrame
) -> pl.DataFrame:
    async with _projection_lock:
        if station not in _projection_cache:
            # the per-station product is ~24 MB of IPC, worth its own line
            started = time.monotonic()
            _projection_cache[station] = await asyncio.to_thread(
                holmes.data.projection.read_projection_data, stations
            )
            elapsed = time.monotonic() - started
            done_print(
                f"Loaded projection data for {station} in {elapsed:.1f}s."
            )
        return _projection_cache[station]


def _run_ensemble(
    filtered: pl.DataFrame,
    hydro_models: list[HydroModel],
    snow_model: SnowModel | None,
    hydro_params: dict[str, list[float]],
    snow: npt.NDArray[np.float64] | None,
    agg_start_year: int,
    agg_end_year: int,
    cache_scope: tuple[str, str, str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    # the calendar columns are identical across members, models and horizons,
    # so they are attached once here rather than per _aggregate call
    members = _with_calendar(filtered).partition_by(
        "member", maintain_order=True
    )
    results: dict[str, Any] = {}
    all_regimes: list[npt.NDArray[np.float64]] = []
    all_indicators: list[dict[str, float]] = []
    for model in hydro_models:
        simulations = _simulate_members(
            members, model, snow_model, hydro_params[model], snow, cache_scope
        )
        member_payload: dict[str, Any] = {}
        regimes: list[npt.NDArray[np.float64]] = []
        indicators_list: list[dict[str, float]] = []
        for frame in members:
            member = frame[0, "member"]
            regime, indicators = _aggregate(
                frame.select("year", "month", "day_of_year").with_columns(
                    pl.Series("simulation", simulations[member])
                ),
                agg_start_year,
                agg_end_year,
            )
            regimes.append(regime)
            indicators_list.append(indicators)
            member_payload[member] = _series_payload(regime, indicators)
        model_regime = _median_regime(regimes)
        model_indicators = _median_indicators(indicators_list)
        results[model] = {
            "members": member_payload,
            "medianRegime": _round(sanitize(model_regime)),
            "medianIndicators": _round_indicators(model_indicators),
        }
        all_regimes.extend(regimes)
        all_indicators.extend(indicators_list)
    median = _series_payload(
        _median_regime(all_regimes), _median_indicators(all_indicators)
    )
    return results, median


def _simulate_members(
    members: list[pl.DataFrame],
    model: HydroModel,
    snow_model: SnowModel | None,
    params: list[float],
    snow: npt.NDArray[np.float64] | None,
    cache_scope: tuple[str, str, str],
) -> dict[str, npt.NDArray[np.float64]]:
    key = (
        *cache_scope,
        model,
        snow_model,
        tuple(params),
        tuple(snow) if snow is not None else None,
    )
    if key not in _simulation_cache:
        hydro = np.array(params, dtype=np.float64)
        _simulation_cache[key] = {
            frame[0, "member"]: holmes.model.simulate(
                frame, model, snow_model, hydro_params=hydro, snow_params=snow
            )
            for frame in members
        }
        while len(_simulation_cache) > max_cached_ensembles:
            del _simulation_cache[next(iter(_simulation_cache))]
    return _simulation_cache[key]


def _run_historical(
    observed: pl.DataFrame,
    hydro_models: list[HydroModel],
    snow_model: SnowModel | None,
    hydro_params: dict[str, list[float]],
    snow: npt.NDArray[np.float64] | None,
    start: date,
    end: date,
) -> dict[str, Any]:
    # the reference is what the models produce under the observed forcing, so
    # the gap to the projections is climate signal rather than model bias;
    # the client only receives the cross-model median. `observed` carries a
    # warmup lead ahead of [start, end]: the models simulate over all of it,
    # but the aggregation keeps the period's own rows only — cut by exact
    # date, because _aggregate's calendar-year window would leak the lead's
    # tail into a mid-year start year. partial edge years are then dropped by
    # min_year_days like everywhere else (a fabricated seasonal extreme is
    # worse than a smaller sample)
    observed = observed.sort("datetime")
    period = pl.col("datetime").is_between(start, end)
    regimes: list[npt.NDArray[np.float64]] = []
    indicators_list: list[dict[str, float]] = []
    for model in hydro_models:
        simulation = holmes.model.simulate(
            observed,
            model,
            snow_model,
            hydro_params=np.array(hydro_params[model], dtype=np.float64),
            snow_params=snow,
        )
        regime, indicators = _aggregate(
            observed.select("datetime")
            .with_columns(pl.Series("simulation", simulation))
            .filter(period),
            start.year,
            end.year,
        )
        regimes.append(regime)
        indicators_list.append(indicators)
    return _series_payload(
        _median_regime(regimes), _median_indicators(indicators_list)
    )


def _aggregate(
    frame: pl.DataFrame, agg_start_year: int, agg_end_year: int
) -> tuple[npt.NDArray[np.float64], dict[str, float]]:
    """Reduce a daily simulation to its regime and seasonal indicators.

    Valid on both the noleap projection calendar and the real observed one:
    the day of year comes from the `_prepare_data` idiom (Feb 29 -> 28, all
    years forced to a common non-leap year).
    """
    if "day_of_year" not in frame.columns:
        frame = _with_calendar(frame)
    frame = frame.filter(
        pl.col("year").is_between(agg_start_year, agg_end_year)
    ).filter(pl.len().over("year") >= min_year_days)
    regime = (
        frame.group_by("day_of_year")
        .agg(pl.col("simulation").mean())
        .sort("day_of_year")
    )
    if regime.height != 365:
        raise RuntimeError(
            f"Expected 365 regime days, got {regime.height}; the record is"
            " too short or has missing days."
        )
    # per year first, then averaged: the indicators describe the typical
    # seasonal extreme, not the extreme of the typical (regime) year
    per_year = frame.group_by("year").agg(
        pl.col("simulation")
        .filter(pl.col("month").is_in([1, 2, 3]))
        .min()
        .alias("winter_min"),
        pl.col("simulation")
        .filter(pl.col("month").is_in([4, 5, 6]))
        .max()
        .alias("spring_max"),
        pl.col("simulation")
        .filter(pl.col("month").is_in([7, 8, 9]))
        .min()
        .alias("summer_min"),
        # autumn deliberately overlaps September so a peak on the summer /
        # autumn boundary is not split between windows
        pl.col("simulation")
        .filter(pl.col("month").is_in([9, 10, 11]))
        .max()
        .alias("autumn_max"),
        pl.col("simulation").mean().alias("mean"),
    )
    indicators = {
        key: float(cast(float, per_year[key].mean()))
        for key in [
            "winter_min",
            "spring_max",
            "summer_min",
            "autumn_max",
            "mean",
        ]
    }
    return regime["simulation"].to_numpy(), indicators


def _with_calendar(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.col("datetime").dt.year().alias("year"),
        pl.col("datetime").dt.month().alias("month"),
        pl.when(
            (pl.col("datetime").dt.month() == 2)
            & (pl.col("datetime").dt.day() == 29)
        )
        .then(pl.col("datetime").dt.replace(day=28))
        .otherwise(pl.col("datetime"))
        .dt.replace(year=2021)
        .dt.ordinal_day()
        .alias("day_of_year"),
    )


def _median_regime(
    regimes: list[npt.NDArray[np.float64]],
) -> npt.NDArray[np.float64]:
    # a day with no finite member yields NaN, which nanmedian reports with a
    # RuntimeWarning that is expected and silenced (the _evaluate_median idiom)
    stack = np.stack(regimes)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmedian(
            np.where(np.isfinite(stack), stack, np.nan), axis=0
        )


def _median_indicators(
    indicators: list[dict[str, float]],
) -> dict[str, float]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return {
            key: float(
                np.nanmedian(
                    [
                        d[key] if np.isfinite(d[key]) else np.nan
                        for d in indicators
                    ]
                )
            )
            for key in indicators[0]
        }


def _series_payload(
    regime: npt.NDArray[np.float64], indicators: dict[str, float]
) -> dict[str, Any]:
    return {
        "regime": _round(sanitize(regime)),
        "indicators": _round_indicators(indicators),
    }


def _round(values: list[float | None]) -> list[float | None]:
    # worst case is ~150k numbers in one reply; 4 decimals halve the JSON at
    # far better than measurement precision (values are mm/day)
    return [None if v is None else round(v, 4) for v in values]


def _round_indicators(indicators: dict[str, float]) -> dict[str, Any]:
    return {
        key: None if not np.isfinite(value) else round(value, 4)
        for key, value in indicators.items()
    }


async def _send_error(
    ws: WebSocket, *, request_id: int | None = None, message: str
) -> None:
    fail_print(message)
    await send(
        ws,
        "projection_error",
        {"requestId": request_id, "message": message},
    )
