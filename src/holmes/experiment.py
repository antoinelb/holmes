import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Literal, NamedTuple, cast, get_args

import altair as alt
import numpy as np
import polars as pl

import holmes.data
import holmes.model
import holmes.utils.api
import holmes.utils.config
from holmes.utils.paths import results_dir
from holmes.utils.plotting import named_colours
from holmes.utils.print import done_print, progress_task

#########
# types #
#########


class Experiment(NamedTuple):
    calibration_station: str
    simulation_station: str
    calibration_period: tuple[date, date]
    simulation_period: tuple[date, date]
    hydro_model: holmes.model.HydroModel | Literal["all"]
    weather_method: holmes.data.weather.WeatherMethod
    objective: holmes.model.Objective
    transformation: holmes.model.Transformation
    warmup_years: int = 3
    with_cemaneige: bool = True


##########
# public #
##########


async def run_experiment() -> None:
    experiments = [
        Experiment(
            calibration_station="pikauba amont",
            simulation_station="pikauba amont",
            calibration_period=(date(1980, 1, 1), date(1984, 12, 31)),
            simulation_period=(date(1980, 1, 1), date(1984, 12, 31)),
            hydro_model="all",
            weather_method="ministry_grid",
            objective="rmse",
            transformation="none",
        ),
        Experiment(
            calibration_station="pikauba amont",
            simulation_station="pikauba amont",
            calibration_period=(date(1980, 1, 1), date(1989, 12, 31)),
            simulation_period=(date(1990, 1, 1), date(1999, 12, 31)),
            hydro_model="all",
            weather_method="ministry_grid",
            objective="rmse",
            transformation="none",
        ),
        Experiment(
            calibration_station="aux écorces",
            simulation_station="pikauba aval",
            calibration_period=(date(2010, 1, 1), date(2019, 12, 31)),
            simulation_period=(date(2000, 1, 1), date(2019, 12, 31)),
            hydro_model="all",
            weather_method="ministry_grid",
            objective="rmse",
            transformation="none",
        ),
        Experiment(
            calibration_station="pikauba amont",
            simulation_station="pikauba aval",
            calibration_period=(date(1990, 1, 1), date(1999, 12, 31)),
            simulation_period=(date(1990, 1, 1), date(1999, 12, 31)),
            hydro_model="all",
            weather_method="ministry_grid",
            objective="rmse",
            transformation="none",
        ),
    ]

    data = read_data()

    _create_timeseries_figs(data)

    for experiment in experiments:
        data = read_data(weather_method=experiment.weather_method)
        await _run_experiment(data, experiment)


def read_data(
    *,
    weather_method: holmes.data.weather.WeatherMethod = "ministry_grid",
    n_stations: int = 3,
) -> pl.DataFrame:
    # the joined products are prebuilt by `holmes download` and shipped in
    # the data archive; experiments never build anything themselves
    return holmes.data.joined.read_joined_data(
        method=weather_method, n_stations=n_stations
    )


###########
# private #
###########


async def _run_experiment(data: pl.DataFrame, experiment: Experiment) -> None:
    path, hash_ = _update_experiment_list(experiment)
    path.mkdir(exist_ok=True)
    results_path = path / "results.csv"

    if experiment.hydro_model == "all":
        if not results_path.exists():
            results = pl.concat(
                await asyncio.gather(
                    *(
                        _run_subexperiment(
                            data,
                            Experiment(
                                **{
                                    **experiment._asdict(),
                                    "hydro_model": model,
                                }
                            ),
                            hash_,
                            path / model,
                        )
                        for model in get_args(holmes.model.HydroModel)
                    )
                )
            )
            results.write_csv(results_path)

    else:
        await _run_subexperiment(data, experiment, hash_, path)
        done_print(f"Ran experiment {hash_}.")


async def _run_subexperiment(
    data: pl.DataFrame, experiment: Experiment, hash_: str, path: Path
) -> pl.DataFrame:
    path.mkdir(exist_ok=True, parents=True)
    params_path = path / "params.json"
    results_path = path / "results.csv"
    calibration_fig_path = path / "calibration.svg"
    simulation_fig_path = path / "simulation.svg"

    if all(
        _path.exists()
        for _path in [
            results_path,
            calibration_fig_path,
            simulation_fig_path,
        ]
    ):
        results = pl.read_csv(results_path)
        done_print(
            f"Experiment {hash_} with model {experiment.hydro_model} already ran."
        )
        return results

    else:
        snow_model = "cemaneige" if experiment.with_cemaneige else None
        experiment_ = pl.DataFrame(
            {
                "calibration_station": experiment.calibration_station,
                "simulation_station": experiment.simulation_station,
                "calibration_period": f"{experiment.calibration_period[0]}-{experiment.calibration_period[1]}",
                "simulation_period": f"{experiment.simulation_period[0]}-{experiment.simulation_period[1]}",
                "hydro_model": experiment.hydro_model,
                "weather_method": experiment.weather_method,
                "objective": experiment.objective,
                "transformation": experiment.transformation,
                "warmup_years": experiment.warmup_years,
                "with_cemaneige": experiment.with_cemaneige,
                "hash": hash_,
            }
        )

        # the warmup lead is prepended before each period rather than taken
        # from inside it, and clamps to the rows that exist before its start
        calibration_data, calibration_warmup = _filter_with_warmup(
            data,
            experiment.calibration_station,
            experiment.calibration_period,
            experiment.warmup_years,
        )
        simulation_data, simulation_warmup = _filter_with_warmup(
            data,
            experiment.simulation_station,
            experiment.simulation_period,
            experiment.warmup_years,
        )

        if params_path.exists():
            with open(params_path) as f:
                params = json.load(f)
                hydro_params = np.array(params["hydro"])
                snow_params = (
                    np.array(params["snow"])
                    if params["snow"] is not None
                    else None
                )
        else:
            hydro_params, snow_params = await holmes.model.calibrate(
                calibration_data,
                cast(holmes.model.HydroModel, experiment.hydro_model),
                objective=experiment.objective,
                snow_model=snow_model,
                transformation=experiment.transformation,
                warmup_steps=calibration_warmup,
            )
            with open(params_path, "w") as f:
                json.dump(
                    {
                        "hydro": list(hydro_params),
                        "snow": list(snow_params)
                        if snow_params is not None
                        else None,
                    },
                    f,
                )

        calibration_data, calibration_results = (
            holmes.model.evaluate_simulation(
                calibration_data,
                cast(holmes.model.HydroModel, experiment.hydro_model),
                snow_model,
                hydro_params=hydro_params,
                snow_params=snow_params,
                warmup_steps=calibration_warmup,
            )
        )
        simulation_data, simulation_results = holmes.model.evaluate_simulation(
            simulation_data,
            cast(holmes.model.HydroModel, experiment.hydro_model),
            snow_model,
            hydro_params=hydro_params,
            snow_params=snow_params,
            warmup_steps=simulation_warmup,
        )
        results = pl.concat(
            [
                experiment_,
                calibration_results.rename(
                    {
                        name: f"calibration_{name}"
                        for name in calibration_results.columns
                    }
                ),
                simulation_results.rename(
                    {
                        name: f"simulation_{name}"
                        for name in simulation_results.columns
                    }
                ),
            ],
            # all three frames are one row; horizontal_extend keeps the
            # pre-2.0 zero-padding semantics without the deprecation
            how="horizontal_extend",
        )
        results.write_csv(results_path)

        _create_timeseries_fig(calibration_data, calibration_fig_path)
        _create_timeseries_fig(simulation_data, simulation_fig_path)

        done_print(
            f"Experiment {hash_} with model {experiment.hydro_model} ran."
        )

        return results


def _filter_with_warmup(
    data: pl.DataFrame,
    station: str,
    period: tuple[date, date],
    warmup_years: int,
) -> tuple[pl.DataFrame, int]:
    # experiments key on the friendly name, unlike the websocket API's id, so
    # this mirrors `api_calibration.filter_data_with_warmup` rather than
    # reusing it. the step count is the actual lead height, so a lead that
    # runs past the start of the record simply gets shorter
    start, end = period
    filtered = (
        data.filter(pl.col("name").str.to_lowercase() == station)
        .filter(
            pl.col("datetime").is_between(
                holmes.model.warmup_start(start, warmup_years), end
            )
        )
        .sort("datetime")
    )
    return filtered, int((filtered["datetime"] < start).sum())


def _update_experiment_list(experiment: Experiment) -> tuple[Path, str]:
    list_path = results_dir / "experiments" / "experiments.json"
    list_path.parent.mkdir(exist_ok=True)

    hash_ = holmes.utils.config.hash_config(experiment._asdict())

    if list_path.exists():
        with open(list_path) as f:
            experiments = json.load(f)
    else:
        experiments = {}

    if hash_ not in experiments:
        experiments[hash_] = holmes.utils.api.convert_for_json(
            experiment._asdict(), dates_as_str=True
        )
        experiments = dict(sorted(experiments.items()))
        with open(list_path, "w") as f:
            json.dump(experiments, f, indent=2)

    return results_dir / "experiments" / hash_, hash_


def _create_timeseries_figs(data: pl.DataFrame) -> None:
    path = results_dir / "catchments"
    partitions = data.partition_by("id")
    with progress_task(
        "Creating timeseries figures...",
        "Created timeseries figures.",
        total=len(partitions),
    ) as current:
        for _data in partitions:
            _path = (
                path
                / f"{_data[0, 'id']}_{_data[0, 'name'].lower().replace(' ', '_')}.svg"
            )
            if not _path.exists():
                _create_timeseries_fig(_data, _path)
            current.increment()


def _create_timeseries_fig(data: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(exist_ok=True, parents=True)

    if "simulation" in data.columns:
        fig = alt.vconcat(
            _create_timeseries_subfig_with_simulation(data),
            _create_timeseries_subfig(data, "mm", "precipitation"),
            _create_timeseries_subfig(data, "°C", "temperature"),
        ).properties(title=f"{data[0, 'name']} ({data[0, 'id']})")
    else:
        fig = alt.vconcat(
            _create_timeseries_subfig(data, "mm", "streamflow"),
            _create_timeseries_subfig(data, "mm", "precipitation"),
            _create_timeseries_subfig(data, "°C", "temperature"),
        ).properties(title=f"{data[0, 'name']} ({data[0, 'id']})")

    fig.save(path)


def _create_timeseries_subfig(
    data: pl.DataFrame, units: str, variable: str
) -> alt.typing.ChartType:
    width = 600
    height = 200

    data = data.select("datetime", variable).with_columns(
        pl.col(variable).is_null().alias("missing")
    )

    lines = (
        alt.Chart(data)
        .mark_line(color=named_colours["black"], size=1)
        .encode(
            x=alt.X("datetime:T", axis=alt.Axis(title="")),
            y=alt.Y(
                f"{variable}:Q", axis=alt.Axis(title=f"{variable} ({units})")
            ),
        )
    )

    missing = (
        data.filter(pl.col("missing"))
        .with_columns(
            (pl.col("datetime").diff().dt.total_days().fill_null(1) > 1)
            .cum_sum()
            .alias("run")
        )
        .group_by("run")
        .agg(
            start=pl.col("datetime").min(),
            end=pl.col("datetime").max(),
        )
    )

    missing_single = (
        alt.Chart(missing.filter(pl.col("end") == pl.col("start")))
        .mark_rule(color=named_colours["red"], opacity=0.15)
        .encode(x="start:T")
    )
    missing_multiple = (
        alt.Chart(missing.filter(pl.col("end") != pl.col("start")))
        .mark_rect(color=named_colours["red"], opacity=0.15)
        .encode(x="start:T", x2="end:T")
    )

    return alt.layer(lines, missing_single, missing_multiple).properties(
        height=height,
        width=width,
    )


def _create_timeseries_subfig_with_simulation(
    data: pl.DataFrame,
) -> alt.typing.ChartType:
    width = 600
    height = 200

    data = data.select("datetime", "streamflow", "simulation").with_columns(
        pl.col("streamflow").is_null().alias("missing")
    )

    observation_lines = (
        alt.Chart(data)
        .mark_line(color=named_colours["black"], size=1)
        .encode(
            x=alt.X("datetime:T", axis=alt.Axis(title="")),
            y=alt.Y("streamflow:Q", axis=alt.Axis(title="streamflow (mm)")),
        )
    )
    simulation_lines = (
        alt.Chart(data)
        .mark_line(color=named_colours["blue"], size=1)
        .encode(x=alt.X("datetime:T"), y=alt.Y("simulation:Q"))
    )

    missing = (
        data.filter(pl.col("missing"))
        .with_columns(
            (pl.col("datetime").diff().dt.total_days().fill_null(1) > 1)
            .cum_sum()
            .alias("run")
        )
        .group_by("run")
        .agg(
            start=pl.col("datetime").min(),
            end=pl.col("datetime").max(),
        )
    )

    missing_single = (
        alt.Chart(missing.filter(pl.col("end") == pl.col("start")))
        .mark_rule(color=named_colours["red"], opacity=0.1)
        .encode(x="start:T")
    )
    missing_multiple = (
        alt.Chart(missing.filter(pl.col("end") != pl.col("start")))
        .mark_rect(color=named_colours["red"], opacity=0.1)
        .encode(x="start:T", x2="end:T")
    )

    return alt.layer(
        observation_lines, simulation_lines, missing_single, missing_multiple
    ).properties(
        height=height,
        width=width,
    )
