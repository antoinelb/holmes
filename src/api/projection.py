from starlette.requests import Request
from starlette.responses import Response
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
        "hydrological_model",
        "catchment",
        "snow_model",
        "params",
        "climate_model",
        "climate_scenario",
        "horizon",
        "theme",
    ]
)
async def _run_projection(
    _: Request,
    hydrological_model: str,
    catchment: str,
    snow_model: str,
    params: list[dict[str, float | str]],
    climate_model: str,
    climate_scenario: str,
    horizon: str,
    theme: str,
) -> Response:
    params_ = {str(param["name"]): float(param["value"]) for param in params}
    projections = hydro.projection.run_projection(
        hydrological_model,
        catchment,
        snow_model,
        params_,
        climate_model,
        climate_scenario,
        horizon,
    )

    fig = hydro.projection.plot_projection(
        projections,
        catchment,
        climate_model,
        climate_scenario,
        horizon,
        template="simple_white" if theme == "light" else None,
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
