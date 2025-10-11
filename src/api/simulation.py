from datetime import datetime, timedelta

import polars as pl
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from src import data, hydro

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


async def _run_simulation(_: Request) -> Response:
    return JSONResponse({})
