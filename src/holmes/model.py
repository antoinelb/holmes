import logging
import threading
from collections.abc import Callable
from datetime import date
from typing import Any, Literal, Protocol, assert_never, cast

import holmes_rs
import numpy as np
import numpy.typing as npt
import polars as pl
from holmes_rs.calibration.sce import Sce

from holmes.utils.print import done_print, load_print

logger = logging.getLogger("holmes")

#########
# types #
#########

Objective = Literal["rmse", "nse", "kge"]
Transformation = Literal["log", "sqrt", "none"]
Algorithm = Literal["sce"]

HydroModel = Literal[
    "gr4j",
    "bucket",
    "cequeau",
    "crec",
    "gardenia",
    "hbv",
    "hymod",
    "ihacres",
    "martine",
    "mohyse",
    "mordor",
    "nam",
    "pdm",
    "sacramento",
    "simhyd",
    "smar",
    "tank",
    "topmodel",
    "wageningen",
    "xinanjiang",
]
SnowModel = Literal["cemaneige"]
PetModel = Literal["oudin"]


class _HydroSimulate(Protocol):
    def __call__(
        self,
        params: npt.NDArray[np.float64],
        precipitation: npt.NDArray[np.float64],
        pet: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]: ...


class _SnowSimulate(Protocol):
    def __call__(
        self,
        params: npt.NDArray[np.float64],
        precipitation: npt.NDArray[np.float64],
        temperature: npt.NDArray[np.float64],
        day_of_year: npt.NDArray[np.uintp],
        elevation_layers: npt.NDArray[np.float64],
        median_elevation: float,
    ) -> npt.NDArray[np.float64]: ...


class _PetSimulate(Protocol):
    def __call__(
        self,
        temperature: npt.NDArray[np.float64],
        day_of_year: npt.NDArray[np.uintp],
        latitude: float,
    ) -> npt.NDArray[np.float64]: ...


##########
# public #
##########


def get_config(
    model: Algorithm,
) -> list[dict[str, str | int | float | bool | None]]:
    """Get calibration algorithm configuration."""
    match model:
        case "sce":
            return [
                {
                    "name": "seed",
                    "min": 0,
                    "max": None,
                    "default": 0,
                    "integer": True,
                },
                {
                    "name": "n_complexes",
                    "min": 1,
                    "max": None,
                    "default": 25,
                    "integer": True,
                },
                {
                    "name": "k_stop",
                    "min": 1,
                    "max": None,
                    "default": 10,
                    "integer": True,
                },
                {
                    "name": "p_convergence_threshold",
                    "min": 0,
                    "max": 1,
                    "default": 0.1,
                    "integer": False,
                },
                {
                    "name": "geometric_range_threshold",
                    "min": 0,
                    "max": None,
                    "default": 0.001,
                    "integer": False,
                },
                {
                    "name": "max_evaluations",
                    "min": 1,
                    "max": None,
                    "default": 50000,
                    "integer": True,
                },
            ]
        case _:  # pragma: no cover
            assert_never(model)


async def calibrate(
    data: pl.DataFrame,
    hydro_model: HydroModel,
    objective: Objective,
    snow_model: SnowModel | None,
    transformation: Transformation,
    warmup_steps: int,
    *,
    algorithm: Algorithm = "sce",
    params: dict[str, Any] | None = None,
    pet_model: PetModel = "oudin",
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64] | None]:
    # Thin async wrapper over the synchronous streaming calibrator, kept so the
    # historical `await calibrate(...)` call sites need no change.
    load_print("Calibrating model...")
    result = calibrate_stream(
        data,
        hydro_model,
        objective,
        snow_model,
        transformation,
        warmup_steps,
        algorithm=algorithm,
        params=params,
        pet_model=pet_model,
    )
    done_print("Calibrated model")
    return result


def calibrate_stream(
    data: pl.DataFrame,
    hydro_model: HydroModel,
    objective: Objective,
    snow_model: SnowModel | None,
    transformation: Transformation,
    warmup_steps: int,
    *,
    algorithm: Algorithm = "sce",
    params: dict[str, Any] | None = None,
    pet_model: PetModel = "oudin",
    callback: Callable[
        [
            int,
            bool,
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
            npt.NDArray[np.float64],
        ],
        None,
    ]
    | None = None,
    stop_event: threading.Event | None = None,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64] | None]:
    # Synchronous so it can serve as a thread body. Every step is streamed to
    # `callback` and `stop_event` provides cooperative cancellation; it prints
    # nothing (the async `calibrate` owns any user-facing progress).
    max_iter = 100_000

    match snow_model:
        case None:
            snow_params = None
        case "cemaneige":
            # the warmup lead precedes the calibration period, so qnbv keeps
            # its calibration-window meaning (and matches the one the client
            # gets from `calibration_data` and replays downstream)
            qnbv = calculate_qnbv(data.slice(warmup_steps))
            snow_params = np.array([0.25, 3.74, qnbv])
        case _:  # pragma: no cover
            assert_never(snow_model)

    (
        day_of_year,
        elevation_layers,
        median_elevation,
        observations,
        pet,
        precipitation,
        temperature,
    ) = _prepare_data(
        data,
        pet_model=pet_model,
        snow_model=snow_model,
        snow_params=snow_params,
    )

    if params is None:
        params = cast(
            dict[str, Any],
            {
                param["name"]: param["default"]
                for param in get_config(algorithm)
            },
        )
    match algorithm:
        case "sce":
            calibration = Sce(
                hydro_model,
                None,
                objective,
                transformation,
                seed=params["seed"],
                n_complexes=params["n_complexes"],
                k_stop=params["k_stop"],
                p_convergence_threshold=params["p_convergence_threshold"],
                geometric_range_threshold=params["geometric_range_threshold"],
                max_evaluations=params["max_evaluations"],
            )
            calibration.init(
                precipitation,
                temperature,
                pet,
                day_of_year,
                elevation_layers,
                median_elevation,
                observations,
                warmup_steps,
            )

            for step_i in range(max_iter):
                done, params_, simulation, objectives = calibration.step(
                    precipitation,
                    temperature,
                    pet,
                    day_of_year,
                    elevation_layers,
                    median_elevation,
                    observations,
                    warmup_steps,
                )

                if callback is not None:
                    callback(step_i, done, params_, simulation, objectives)

                if done or (stop_event is not None and stop_event.is_set()):
                    break

            return params_, snow_params

        case _:  # pragma: no cover
            assert_never(algorithm)


def simulate_manual(
    data: pl.DataFrame,
    hydro_model: HydroModel,
    snow_model: SnowModel | None,
    transformation: Transformation,
    warmup_steps: int,
    *,
    hydro_params: npt.NDArray[np.float64],
    pet_model: PetModel = "oudin",
) -> tuple[npt.NDArray[np.float64], dict[str, float]]:
    match snow_model:
        case None:
            snow_params = None
        case "cemaneige":
            # scored window only, like `calibrate_stream`
            snow_params = np.array(
                [0.25, 3.74, calculate_qnbv(data.slice(warmup_steps))]
            )
        case _:  # pragma: no cover
            assert_never(snow_model)

    (
        _,
        _,
        _,
        observations,
        pet,
        precipitation,
        _,
    ) = _prepare_data(
        data,
        pet_model=pet_model,
        snow_model=snow_model,
        snow_params=snow_params,
    )

    simulation = _get_hydro_model(hydro_model)(
        hydro_params, precipitation, pet
    )
    objectives = _evaluate_objectives(
        observations, simulation, transformation, warmup_steps
    )

    return simulation, objectives


def simulate_with_metrics(
    data: pl.DataFrame,
    hydro_model: HydroModel,
    snow_model: SnowModel | None,
    warmup_steps: int,
    *,
    hydro_params: npt.NDArray[np.float64],
    snow_params: npt.NDArray[np.float64] | None,
    pet_model: PetModel = "oudin",
) -> tuple[npt.NDArray[np.float64], dict[str, float]]:
    """Simulate with fixed parameters and score the display metrics.

    Unlike `simulate_manual`, the snow parameters are supplied by the
    caller rather than recomputed from `data`: a simulation run scores
    parameters fitted on another period, so the calibrated qnbv is
    carried over (the same convention as `run_experiment`).
    """
    (
        _,
        _,
        _,
        observations,
        pet,
        precipitation,
        _,
    ) = _prepare_data(
        data,
        pet_model=pet_model,
        snow_model=snow_model,
        snow_params=snow_params,
    )

    simulation = _get_hydro_model(hydro_model)(
        hydro_params, precipitation, pet
    )
    metrics = evaluate_simulation_metrics(
        observations, simulation, warmup_steps
    )

    return simulation, metrics


def simulate(
    data: pl.DataFrame,
    hydro_model: HydroModel,
    snow_model: SnowModel | None,
    *,
    hydro_params: npt.NDArray[np.float64],
    snow_params: npt.NDArray[np.float64] | None,
    pet_model: PetModel = "oudin",
) -> npt.NDArray[np.float64]:
    """Simulate with fixed parameters, no observations, no scoring.

    The projection entry point: `data` needs no `streamflow` column, only
    `datetime`, `lat`, `elevation_layers`, `precipitation` and `temperature`.
    Like `simulate_with_metrics`, the snow parameters are carried over from
    calibration rather than recomputed from `data`.
    """
    (
        _,
        _,
        _,
        _,
        pet,
        precipitation,
        _,
    ) = _prepare_data(
        data,
        pet_model=pet_model,
        snow_model=snow_model,
        snow_params=snow_params,
    )

    return _get_hydro_model(hydro_model)(hydro_params, precipitation, pet)


def evaluate_simulation_metrics(
    observations: npt.NDArray[np.float64],
    simulation: npt.NDArray[np.float64],
    warmup_steps: int,
) -> dict[str, float]:
    """Score a simulation with the six display metrics (optimum 1)."""
    # Same guard order as `_evaluate_objectives`: cut the warmup, penalize
    # a degenerate simulation over the full window, then drop observation
    # gaps before any transform so a gap can never become log(1e-5).
    observations = observations[warmup_steps:]
    simulation = simulation[warmup_steps:]

    # These are display values, not optimizer objectives, so a degenerate
    # metric maps to NaN (dropped client-side) rather than a worst-case
    # ordering value like the calibration objectives' ±inf.
    penalties = {
        "kge": np.nan,
        "kge_sqrt": np.nan,
        "kge_log": np.nan,
        "mean_bias": np.nan,
        "deviation_bias": np.nan,
        "correlation": np.nan,
    }
    if not np.all(np.isfinite(simulation)):
        return penalties

    kept = np.isfinite(observations)
    observations = observations[kept]
    simulation = simulation[kept]
    if observations.size == 0:
        return penalties

    # Guards are per metric: a negative simulated flow makes the sqrt pair
    # NaN, which must sink kge_sqrt without taking the raw KGE with it.
    with np.errstate(invalid="ignore", divide="ignore"):
        return {
            "kge": _penalize_degenerate(
                holmes_rs.metrics.calculate_kge,
                observations,
                simulation,
                np.nan,
            ),
            "kge_sqrt": _penalize_degenerate(
                holmes_rs.metrics.calculate_kge,
                np.sqrt(observations),
                np.sqrt(simulation),
                np.nan,
            ),
            "kge_log": _penalize_degenerate(
                holmes_rs.metrics.calculate_kge,
                np.log(np.maximum(observations, 1e-5)),
                np.log(np.maximum(simulation, 1e-5)),
                np.nan,
            ),
            "mean_bias": float(np.mean(simulation) / np.mean(observations)),
            "deviation_bias": float(np.std(simulation) / np.std(observations)),
            "correlation": float(np.corrcoef(observations, simulation)[0, 1]),
        }


def evaluate_simulation(
    data: pl.DataFrame,
    hydro_model: HydroModel,
    snow_model: SnowModel | None,
    *,
    hydro_params: npt.NDArray[np.float64],
    snow_params: npt.NDArray[np.float64] | None,
    pet_model: PetModel = "oudin",
    warmup_steps: int = 0,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    pass
    (
        _,
        _,
        _,
        _,
        pet,
        precipitation,
        _,
    ) = _prepare_data(
        data,
        pet_model=pet_model,
        snow_model=snow_model,
        snow_params=snow_params,
    )

    simulate = _get_hydro_model(hydro_model)

    simulation = simulate(hydro_params, precipitation, pet)

    data = data.with_columns(
        pl.Series("simulation", simulation),
        pl.when(pl.col("datetime").dt.month().is_in([12, 1, 2]))
        .then(pl.lit("djf"))
        .when(pl.col("datetime").dt.month().is_in([3, 4, 5]))
        .then(pl.lit("mam"))
        .when(pl.col("datetime").dt.month().is_in([6, 7, 8]))
        .then(pl.lit("jja"))
        .otherwise(pl.lit("son"))
        .alias("season"),
    )
    # the model spins up on the leading `warmup_steps` rows; dropping them
    # here keeps both the metrics and the returned figure frame on the
    # requested period
    data = data.slice(warmup_steps)
    evaluation_data = data.filter(
        pl.col("streamflow").is_not_null() & pl.col("simulation").is_not_null()
    )

    year_metrics = {
        "rmse": holmes_rs.metrics.calculate_rmse(
            evaluation_data["streamflow"].to_numpy(),
            evaluation_data["simulation"].to_numpy(),
        ),
        "kge": holmes_rs.metrics.calculate_kge(
            evaluation_data["streamflow"].to_numpy(),
            evaluation_data["simulation"].to_numpy(),
        ),
    }
    season_metrics = {
        f"{name}_{_data[0, 'season']}": metric(
            _data["streamflow"].to_numpy(), _data["simulation"].to_numpy()
        )
        for _data in evaluation_data.partition_by("season")
        for name, metric in (
            ("rmse", holmes_rs.metrics.calculate_rmse),
            ("kge", holmes_rs.metrics.calculate_kge),
        )
    }
    metrics = pl.DataFrame(
        [
            {
                **year_metrics,
                **season_metrics,
            }
        ]
    )

    return data, metrics


def calculate_qnbv(
    data: pl.DataFrame, *, lim_inf: float = -1, lim_sup: float = 3
) -> float:
    return cast(
        float,
        data.select("id", "datetime", "precipitation", "temperature")
        .with_columns(
            (
                1
                - (
                    (pl.col("temperature") - lim_inf) / (lim_sup - lim_inf)
                ).clip(0, 1)
            ).alias("precipitation_solid_fraction")
        )
        .with_columns(
            (
                pl.col("precipitation")
                * pl.col("precipitation_solid_fraction")
            ).alias("solid_fraction")
        )
        .group_by(pl.col("datetime").dt.year())
        .agg(pl.col("solid_fraction").sum())["solid_fraction"]
        .mean(),
    )


def warmup_start(start: date, warmup_years: int) -> date:
    """First day of the warmup lead, `warmup_years` calendar years before
    `start`. Clamping to the data actually available is the caller's job."""
    if warmup_years < 0:
        raise ValueError(f"`warmup_years` must be >= 0, got {warmup_years}.")
    try:
        return start.replace(year=start.year - warmup_years)
    except ValueError:  # Feb 29 with a non-leap target year
        return start.replace(year=start.year - warmup_years, day=28)


###########
# private #
###########


def _get_hydro_model(
    model: HydroModel,
) -> _HydroSimulate:
    match model:
        case "gr4j":
            return holmes_rs.hydro.gr4j.simulate
        case "bucket":
            return holmes_rs.hydro.bucket.simulate
        case "cequeau":
            return holmes_rs.hydro.cequeau.simulate
        case "crec":
            return holmes_rs.hydro.crec.simulate
        case "gardenia":
            return holmes_rs.hydro.gardenia.simulate
        case "hbv":
            return holmes_rs.hydro.hbv.simulate
        case "hymod":
            return holmes_rs.hydro.hymod.simulate
        case "ihacres":
            return holmes_rs.hydro.ihacres.simulate
        case "martine":
            return holmes_rs.hydro.martine.simulate
        case "mohyse":
            return holmes_rs.hydro.mohyse.simulate
        case "mordor":
            return holmes_rs.hydro.mordor.simulate
        case "nam":
            return holmes_rs.hydro.nam.simulate
        case "pdm":
            return holmes_rs.hydro.pdm.simulate
        case "sacramento":
            return holmes_rs.hydro.sacramento.simulate
        case "simhyd":
            return holmes_rs.hydro.simhyd.simulate
        case "smar":
            return holmes_rs.hydro.smar.simulate
        case "tank":
            return holmes_rs.hydro.tank.simulate
        case "topmodel":
            return holmes_rs.hydro.topmodel.simulate
        case "wageningen":
            return holmes_rs.hydro.wageningen.simulate
        case "xinanjiang":
            return holmes_rs.hydro.xinanjiang.simulate
        case _:  # pragma: no cover
            assert_never(model)


def _get_snow_model(
    model: SnowModel,
) -> _SnowSimulate:
    match model:
        case "cemaneige":
            return holmes_rs.snow.cemaneige.simulate
        case _:  # pragma: no cover
            assert_never(model)


def _get_pet_model(
    model: PetModel,
) -> _PetSimulate:
    match model:
        case "oudin":
            return holmes_rs.pet.oudin.simulate
        case _:  # pragma: no cover
            assert_never(model)


def _evaluate_objectives(
    observations: npt.NDArray[np.float64],
    simulation: npt.NDArray[np.float64],
    transformation: Transformation,
    warmup_steps: int,
) -> dict[str, float]:
    # Faithful port of `evaluate_simulation` in the Rust SCE reference so manual
    # objectives match `Sce.step`'s to numerical precision.
    observations = observations[warmup_steps:]
    simulation = simulation[warmup_steps:]

    # A non-finite value anywhere in the simulated window signals a degenerate
    # parameter set. Checked over the FULL window, before dropping gaps, so a
    # gap coinciding with the NaN cannot mask it.
    if not np.all(np.isfinite(simulation)):
        return {"rmse": np.inf, "nse": -np.inf, "kge": -np.inf}

    # Score only where a streamflow observation exists (nulls arrive as NaN).
    # MUST run before the transform: `np.maximum(nan, 1e-5)` returns 1e-5, so a
    # gap would otherwise become log(1e-5) rather than being dropped.
    kept = np.isfinite(observations)
    observations = observations[kept]
    simulation = simulation[kept]

    match transformation:
        case "log":
            observations = np.log(np.maximum(observations, 1e-5))
            simulation = np.log(np.maximum(simulation, 1e-5))
        case "sqrt":
            observations = np.sqrt(observations)
            simulation = np.sqrt(simulation)
        case "none":
            pass
        case _:  # pragma: no cover
            assert_never(transformation)

    # sqrt of a negative simulated value yields NaN at a scored step; penalize
    # rather than crash. Rust checks only the simulations here.
    if not np.all(np.isfinite(simulation)):
        return {"rmse": np.inf, "nse": -np.inf, "kge": -np.inf}

    return {
        "rmse": _penalize_degenerate(
            holmes_rs.metrics.calculate_rmse, observations, simulation, np.inf
        ),
        "nse": _penalize_degenerate(
            holmes_rs.metrics.calculate_nse, observations, simulation, -np.inf
        ),
        "kge": _penalize_degenerate(
            holmes_rs.metrics.calculate_kge, observations, simulation, -np.inf
        ),
    }


def _penalize_degenerate(
    metric: Callable[
        [npt.NDArray[np.float64], npt.NDArray[np.float64]], float
    ],
    observations: npt.NDArray[np.float64],
    simulation: npt.NDArray[np.float64],
    penalty: float,
) -> float:
    # Degenerate parameter sets (e.g. constant observations) make a metric
    # undefined; map that to the metric's worst-case penalty.
    try:
        return metric(observations, simulation)
    except Exception:
        return penalty


def _prepare_data(
    data: pl.DataFrame,
    *,
    pet_model: PetModel,
    snow_model: SnowModel | None,
    snow_params: npt.NDArray[np.float64] | None,
) -> tuple[
    npt.NDArray[np.uintp],  # day_of_year
    npt.NDArray[np.float64],  # elevation_layers
    float,  # median_elevation
    npt.NDArray[np.float64],  # observations
    npt.NDArray[np.float64],  # pet
    npt.NDArray[np.float64],  # precipitation
    npt.NDArray[np.float64],  # temperature
]:
    # Handle leap years by setting February 29 to 28 so as not to lose data and
    # setting all years to 2021. This can be done because the actual date is
    # only used to determine the day of year and a difference of 1 day doesn't
    # change anything.
    data = data.with_columns(
        pl.when(
            (pl.col("datetime").dt.month() == 2)
            & (pl.col("datetime").dt.day() == 29)
        )
        .then(pl.col("datetime").dt.replace(day=28))
        .otherwise(pl.col("datetime"))
        .dt.replace(year=2021)
        .alias("datetime")
    )

    day_of_year = data["datetime"].dt.ordinal_day().to_numpy().astype(np.uintp)
    elevation_layers = np.array(data[0, "elevation_layers"])
    latitude = data[0, "lat"]
    # projection frames carry no observations; a NaN column keeps the return
    # shape identical for every caller
    observations = (
        data["streamflow"].to_numpy()
        if "streamflow" in data.columns
        else np.full(data.height, np.nan)
    )
    precipitation = _fill_missing(
        data["precipitation"].to_numpy(), "precipitation"
    )
    temperature = _fill_missing(data["temperature"].to_numpy(), "temperature")
    # Hoisted above the snow branch: it is returned unconditionally, so leaving
    # it inside would raise UnboundLocalError when `snow_model` is None.
    median_elevation = float(np.median(elevation_layers))

    if snow_model is not None:
        if snow_params is None:
            raise ValueError(
                "If a snow model is given, then `snow_params` must be an array."
            )
        snow_simulate = _get_snow_model(snow_model)
        precipitation = snow_simulate(
            snow_params,
            precipitation,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )

    pet_simulate = _get_pet_model(pet_model)
    pet = pet_simulate(temperature, day_of_year, latitude)

    return (
        day_of_year,
        elevation_layers,
        median_elevation,
        observations,
        pet,
        precipitation,
        temperature,
    )


def _fill_missing(
    data: npt.NDArray[np.float64], variable: str
) -> npt.NDArray[np.float64]:
    data = data.copy()
    is_nan = np.isnan(data)
    if (is_nan & (np.r_[True, is_nan[:-1]] | np.r_[is_nan[1:], True])).any():
        raise RuntimeError(
            f"There is at least one instance of more than one missing value in a row for `{variable}`."
        )
    idx = np.arange(len(data))
    data[is_nan] = np.interp(idx[is_nan], idx[~is_nan], data[~is_nan])
    return data
