import polars as pl
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import BaseRoute, Route

from src import hydro
from src.utils.print import format_list

from .utils import JSONResponse, with_json_params

##########
# public #
##########


def get_routes() -> list[BaseRoute]:
    return [
        Route(
            "/run",
            endpoint=_run_simulation,
            methods=["POST"],
        ),
    ]


###########
# private #
###########


@with_json_params(args=["configs", "multimodel"])
async def _run_simulation(
    _: Request,
    configs: list[dict[str, str | dict[str, float]]],
    multimodel: bool,
) -> Response:
    if len(configs) == 0:
        return PlainTextResponse(
            "At least one config must be given.", status_code=400
        )
    try:
        [_validate_config(config) for config in configs]
    except ValueError as exc:
        return PlainTextResponse(str(exc), status_code=400)

    if len(set([config["catchment"] for config in configs])) != 1:
        return PlainTextResponse(
            "You can't compare multiple catchments together.", status_code=400
        )

    _simulations = [
        _run_single_simulation(
            config["hydrological_model"],  # type: ignore
            config["catchment"],  # type: ignore
            config["snow_model"],  # type: ignore
            config["simulation_start"],  # type: ignore
            config["simulation_end"],  # type: ignore
            {param["name"]: param["value"] for param in config["params"]},  # type: ignore
        )
        for config in configs
    ]

    simulations = pl.concat(
        [
            _simulations[0].select(
                "date", "flow", pl.col("simulation").alias("simulation_1")
            ),
            *[
                simulation.select(
                    pl.col("simulation").alias(f"simulation_{i+2}")
                )
                for i, simulation in enumerate(_simulations[1:])
            ],
        ],
        how="horizontal",
    )

    if multimodel:
        simulations = simulations.with_columns(
            pl.mean_horizontal(r"^simulation_\d+$").alias("multimodel")
        )

    fig = hydro.simulation.plot_simulation(simulations)

    return JSONResponse({"fig": fig.to_json()})


def _validate_config(config: dict[str, str | dict[str, float]]) -> None:
    needed_keys = [
        "hydrological_model",
        "catchment",
        "snow_model",
        "simulation_start",
        "simulation_end",
        "params",
    ]
    if not all(key in config for key in needed_keys):
        raise ValueError(
            "Missing key(s) : {}".format(
                format_list([key for key in needed_keys if key not in config])
            )
        )


def _run_single_simulation(
    hydrological_model: str,
    catchment: str,
    snow_model: str,
    simulation_start: str,
    simulation_end: str,
    params: dict[str, float],
) -> pl.DataFrame:
    data_ = hydro.read_transformed_hydro_data(
        catchment, simulation_start, simulation_end, snow_model
    )
    simulation = hydro.run_model(data_, hydrological_model, params)
    return data_.with_columns(pl.Series("simulation", simulation))


def _combine_simulation_results(
    simulations: list[dict[str, pl.DataFrame | dict[str, float]]],
) -> tuple[pl.DataFrame, dict[str, dict[str, float | list[float]]]]:
    data = pl.concat(
        [
            simulations[0]["data"].rename({"simulation": "simulation_1"}),  # type: ignore
            *[
                simulation.select(
                    pl.col("simulation").alias(f"simulation_{i+2}")
                )
                for i, simulation in enumerate(simulations[1:])
            ],
        ],
        how="horizontal",
    )
    results = {
        key: {
            "optimal": hydro.get_optimal_for_criteria(key),  # type: ignore
            "simulations": [
                simulation["result"][key] for simulation in simulations
            ],
        }
        for key in simulations[0]["result"].keys()  # type: ignore
    }
    return data, results
