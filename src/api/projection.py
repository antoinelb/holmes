from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import BaseRoute, Route

from src import data, hydro
from src.utils.print import format_list

from .utils import JSONResponse, with_json_params, with_query_string_params

##########
# public #
##########


def get_routes() -> list[BaseRoute]:
    return [
        Route(
            "/config",
            endpoint=_get_available_config,
            methods=["GET"],
        ),
        Route(
            "/run",
            endpoint=_run_projection,
            methods=["POST"],
        ),
    ]


###########
# private #
###########


@with_query_string_params(args=["catchment"])
async def _get_available_config(_: Request, catchment: str) -> Response:
    info = data.read_projection_info(catchment)
    return JSONResponse(info)


@with_json_params(
    args=[
        "configs",
        "climate_model",
        "climate_scenario",
        "horizon",
        "multimodel",
    ]
)
async def _run_projection(
    _: Request,
    configs: list[dict[str, str | dict[str, float]]],
    climate_model: str,
    climate_scenario: str,
    horizon: str,
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

    if len(configs) != 1:
        return PlainTextResponse(
            "Projections for multiple configs hasn't been implemented yet.",
            status_code=400,
        )

    projections = hydro.projection.run_projection(
        configs[0], climate_model, climate_scenario, horizon
    )

    fig = hydro.projection.plot_projection(
        projections,
        configs[0],
        climate_model,
        climate_scenario,
        horizon,
        multimodel,
    )

    return JSONResponse({"fig": fig.to_json()})


def _validate_config(config: dict[str, str | dict[str, float]]) -> None:
    needed_keys = [
        "hydrological_model",
        "catchment",
        "snow_model",
        "params",
    ]
    if not all(key in config for key in needed_keys):
        raise ValueError(
            "Missing key(s) : {}".format(
                format_list([key for key in needed_keys if key not in config])
            )
        )
