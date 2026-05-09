import itertools
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, cast, get_args

import holmes_rs
import numpy as np
import numpy.typing as npt
import polars as pl
import tqdm
from holmes.data import (
    get_available_catchments,
    read_cemaneige_info,
    read_data,
)
from holmes.models.calibration import Objective, Transformation
from holmes.models.hydro import HydroModel, get_model
from holmes.models.utils import evaluate

experiment_dir = Path(__file__).parent / ".." / "data" / "experiments"


def main() -> None:
    seeds = [0]
    catchments = get_available_catchments()
    models = get_args(HydroModel)
    transformations = get_args(Transformation)
    objectives = get_args(Objective)

    experiments = _determine_experiments(
        catchments, models, transformations, objectives, seeds
    )
    existing = _read_existing_experiments()
    to_run = experiments.join(
        existing,
        how="anti",
        on=[
            "catchment",
            "model",
            "cemaneige",
            "transformation",
            "objective",
            "seed",
        ],
    ).with_row_index("id", offset=len(existing))
    _run_experiments(to_run)


def _read_existing_experiments() -> pl.DataFrame:
    path = experiment_dir / "experiments.csv"
    if path.exists():
        return pl.read_csv(path, try_parse_dates=True)
    else:
        return pl.DataFrame(
            schema={
                "id": pl.Int64,
                "catchment": pl.String,
                "model": pl.String,
                "cemaneige": pl.Boolean,
                "transformation": pl.String,
                "objective": pl.String,
                "seed": pl.Int64,
                "calibration_warmup_start": pl.Date,
                "calibration_start": pl.Date,
                "calibration_end": pl.Date,
                "simulation_warmup_start": pl.Date,
                "simulation_start": pl.Date,
                "simulation_end": pl.Date,
                "ran_on": pl.Datetime,
                "calibration_kge_none": pl.Float64,
                "calibration_kge_sqrt": pl.Float64,
                "calibration_kge_log": pl.Float64,
                "simulation_kge_none": pl.Float64,
                "simulation_kge_sqrt": pl.Float64,
                "simulation_kge_log": pl.Float64,
            }
        )


def _write_experiments(experiments: pl.DataFrame) -> None:
    path = experiment_dir / "experiments.csv"
    path.parent.mkdir(exist_ok=True, parents=True)
    experiments.write_csv(path)


def _determine_experiments(
    catchments: tuple[tuple[str, bool, tuple[str, str]], ...],
    models: tuple[str, ...],
    transformations: tuple[str, ...],
    objectives: tuple[str, ...],
    seeds: list[int],
) -> pl.DataFrame:
    periods = _create_periods(catchments)
    experiments = pl.DataFrame(
        [
            {
                "catchment": catchment,
                "model": model,
                "cemaneige": snow,
                "transformation": transformation,
                "objective": objective,
                "seed": seed,
            }
            for (
                catchment,
                has_snow,
                _,
            ), model, transformation, objective, seed in itertools.product(
                catchments, models, transformations, objectives, seeds
            )
            for snow in ((True, False) if has_snow else (False,))
        ]
    ).join(periods, on="catchment")
    return experiments


def _create_periods(
    catchments: tuple[tuple[str, bool, tuple[str, str]], ...],
) -> pl.DataFrame:
    data = (
        pl.DataFrame(
            [
                {
                    "catchment": catchment,
                    "calibration_warmup_start": start,
                    "simulation_end": end,
                }
                for catchment, _, (start, end) in catchments
            ]
        )
        .with_columns(
            pl.col("calibration_warmup_start").str.strptime(pl.Date, "%F"),
            pl.col("simulation_end").str.strptime(pl.Date, "%F"),
        )
        .with_columns(
            pl.col("calibration_warmup_start")
            .dt.offset_by("3y")
            .alias("calibration_start"),
        )
        .with_columns(
            (
                pl.col("calibration_start")
                + (pl.col("simulation_end") - pl.col("calibration_start")) / 2
            ).alias("calibration_end")
        )
        .with_columns(
            pl.col("calibration_end")
            .dt.offset_by("1d")
            .alias("simulation_start")
        )
        .with_columns(
            pl.col("simulation_start")
            .dt.offset_by("-3y")
            .alias("simulation_warmup_start"),
        )
    )
    return data


def _run_experiments(experiments: pl.DataFrame) -> pl.DataFrame:
    for experiment in load_progress(
        experiments.to_dicts(), "Running experiments..."
    ):
        try:
            _run_experiment(experiment)
        except Exception:
            print("Error running experiment:")
            print(experiment)
    print("Ran all new experiments.")
    return _read_existing_experiments()


def _run_experiment(
    experiment: dict[str, str | int | float | bool | datetime],
) -> None:
    model = cast(str, experiment["model"])
    objective = cast(str, experiment["objective"])
    transformation = cast(str, experiment["transformation"])
    seed = cast(int, experiment["seed"])
    catchment = cast(str, experiment["catchment"])
    calibration_warmup_start = cast(
        datetime, experiment["calibration_warmup_start"]
    )
    calibration_start = cast(datetime, experiment["calibration_start"])
    calibration_end = cast(datetime, experiment["calibration_end"])
    simulation_warmup_start = cast(
        datetime, experiment["simulation_warmup_start"]
    )
    simulation_start = cast(datetime, experiment["simulation_start"])
    simulation_end = cast(datetime, experiment["simulation_end"])
    snow = cast(bool, experiment["cemaneige"])
    simulate = get_model(cast(HydroModel, model))

    data, precipitation, pet, observations = _prepare_data(
        catchment, calibration_warmup_start, simulation_end, snow
    )

    (
        calibration_precipitation,
        calibration_pet,
        calibration_observations,
        calibration_warmup_steps,
    ) = _select_data(
        calibration_warmup_start,
        calibration_start,
        calibration_end,
        data,
        precipitation,
        pet,
        observations,
    )
    (
        simulation_precipitation,
        simulation_pet,
        simulation_observations,
        simulation_warmup_steps,
    ) = _select_data(
        simulation_warmup_start,
        simulation_start,
        simulation_end,
        data,
        precipitation,
        pet,
        observations,
    )

    params, calibration_metrics = _calibrate(
        model,
        objective,
        transformation,
        seed,
        calibration_precipitation,
        calibration_pet,
        calibration_observations,
        calibration_warmup_steps,
    )

    calibration_simulation = simulate(
        params, calibration_precipitation, calibration_pet
    )
    calibration_observations = calibration_observations[
        calibration_warmup_steps:
    ]
    calibration_simulation = calibration_simulation[calibration_warmup_steps:]
    calibration_kge_none = evaluate(
        calibration_observations, calibration_simulation, "kge", "none"
    )
    calibration_kge_sqrt = evaluate(
        calibration_observations, calibration_simulation, "kge", "sqrt"
    )
    calibration_kge_log = evaluate(
        calibration_observations, calibration_simulation, "kge", "log"
    )

    simulation_simulation = simulate(
        params, simulation_precipitation, simulation_pet
    )
    simulation_observations = simulation_observations[simulation_warmup_steps:]
    simulation_simulation = simulation_simulation[simulation_warmup_steps:]
    simulation_kge_none = evaluate(
        simulation_observations, simulation_simulation, "kge", "none"
    )
    simulation_kge_sqrt = evaluate(
        simulation_observations, simulation_simulation, "kge", "sqrt"
    )
    simulation_kge_log = evaluate(
        simulation_observations, simulation_simulation, "kge", "log"
    )

    experiments = _read_existing_experiments()

    experiment = {
        **experiment,
        "id": len(experiments),
        "ran_on": datetime.now(),
        "calibration_kge_none": calibration_kge_none,
        "calibration_kge_sqrt": calibration_kge_sqrt,
        "calibration_kge_log": calibration_kge_log,
        "simulation_kge_none": simulation_kge_none,
        "simulation_kge_sqrt": simulation_kge_sqrt,
        "simulation_kge_log": simulation_kge_log,
    }

    experiments = pl.concat(
        [experiments, pl.DataFrame([experiment])], how="diagonal"
    )
    _write_experiments(experiments)


def _prepare_data(
    catchment: str, start: datetime, end: datetime, snow: bool
) -> tuple[
    pl.DataFrame,
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
]:
    pass
    data, _ = read_data(catchment, start.strftime("%F"), end.strftime("%F"))

    precipitation = data["precipitation"].to_numpy()
    pet = data["pet"].to_numpy()
    day_of_year = (
        data.select((pl.col("date").dt.ordinal_day() - 1).mod(365) + 1)["date"]
        .to_numpy()
        .astype(np.uintp)
    )

    observations = data["streamflow"].to_numpy()

    if snow:
        metadata = read_cemaneige_info(catchment)
        temperature = data["temperature"].to_numpy()
        elevation_layers = np.array(metadata["altitude_layers"])
        median_elevation = metadata["median_altitude"]
        qnbv = metadata["qnbv"]
        snow_params = np.array([0.25, 3.74, qnbv])
        precipitation = holmes_rs.snow.cemaneige.simulate(
            snow_params,
            precipitation,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )
    else:
        temperature = None
        elevation_layers = None
        median_elevation = None
        qnbv = None

    return data, precipitation, pet, observations


def _select_data(
    warmup_start: datetime,
    start: datetime,
    end: datetime,
    data: pl.DataFrame,
    precipitation: npt.NDArray[np.float64],
    pet: npt.NDArray[np.float64],
    observations: npt.NDArray[np.float64],
) -> tuple[
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    int,
]:
    data = data.with_row_index()
    _warmup_start = data.filter(pl.col("date") == warmup_start)[0, "index"]
    _start = data.filter(pl.col("date") == start)[0, "index"]
    _end = data.filter(pl.col("date") == end)[0, "index"]

    precipitation = precipitation[_warmup_start : _end + 1]
    pet = pet[_warmup_start : _end + 1]
    observations = observations[_warmup_start : _end + 1]
    warmup_steps = _start - _warmup_start

    return precipitation, pet, observations, warmup_steps


def _calibrate(
    model: str,
    objective: str,
    transformation: str,
    seed: int,
    precipitation: npt.NDArray[np.float64],
    pet: npt.NDArray[np.float64],
    observations: npt.NDArray[np.float64],
    warmup_steps: int,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    max_iter = 100_000
    n_complexes = 25
    k_stop = 10
    p_convergence_threshold = 0.1
    geometric_range_threshold = 0.001
    max_evaluations = 5000
    calibration = holmes_rs.calibration.sce.Sce(
        model,
        None,
        objective,
        transformation,
        seed=seed,
        n_complexes=n_complexes,
        k_stop=k_stop,
        p_convergence_threshold=p_convergence_threshold,
        geometric_range_threshold=geometric_range_threshold,
        max_evaluations=max_evaluations,
    )
    calibration.init(
        precipitation,
        None,  # temperature isn't needed without snow
        pet,
        None,  # day_of_year isn't needed without snow
        None,  # elevation_layers isn't needed without snow
        None,  # median_elevation isn't needed without snow
        observations,
        warmup_steps,
    )
    for _ in range(max_iter):
        done, params, simulation, objectives = calibration.step(
            precipitation,
            None,  # temperature isn't needed without snow
            pet,
            None,  # day_of_year isn't needed without snow
            None,  # elevation_layers isn't needed without snow
            None,  # median_elevation isn't needed without snow
            observations,
            warmup_steps,
        )
        if done:
            break
    return params, objectives


def load_progress(
    iter_: Iterable[Any],
    text: str,
    symbol: str = "*",
    indent: int = 0,
    echo: bool = True,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Any]:
    if echo:
        return tqdm.tqdm(
            iter_,
            f"{' ' * indent}[{symbol}] {text}",
            *args,
            leave=False,
            position=0,
            file=sys.stdout,
            **kwargs,
        )
    else:
        return iter_


if __name__ == "__main__":
    main()
