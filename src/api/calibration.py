from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Route

from src import data

from .utils import JSONResponse

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
    ]


###########
# private #
###########


async def _get_available_config(_: Request) -> Response:
    catchments = data.get_available_catchments()
    config = {
        "hydrological_model": ["GR4J"],
        "catchment": catchments,
        "snow_model": ["none", "CemaNeige"],
        "objective_criteria": ["RMSE", "NSE", "KGE"],
        "objective_streamflow": [
            "Low Flows: log",
            "Medium Flows: sqrt",
            "High Flows: none",
        ],
        "algorithm": ["Manual", "Automatic - SCE"],
    }
    return JSONResponse(config)
