import importlib.metadata

from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles

from holmes.utils.paths import static_dir

from . import calibration, projection, simulation

##########
# public #
##########


def get_routes() -> list[BaseRoute]:
    return [
        Route("/", endpoint=_index, methods=["GET"]),
        Route("/ping", endpoint=_ping, methods=["GET"]),
        Route("/health", endpoint=_health, methods=["GET"]),
        Route("/version", endpoint=_get_version, methods=["GET"]),
        Mount(
            "/static",
            app=StaticFiles(directory=str(static_dir.absolute())),
        ),
        Mount("/calibration", routes=calibration.get_routes()),
        Mount("/simulation", routes=simulation.get_routes()),
        Mount("/projection", routes=projection.get_routes()),
    ]


###########
# private #
###########


async def _ping(_: Request) -> Response:
    return PlainTextResponse("Pong!")


async def _health(_: Request) -> Response:
    """Health check endpoint for monitoring."""
    return PlainTextResponse("OK")


async def _get_version(_: Request) -> Response:
    try:
        return PlainTextResponse(importlib.metadata.version("holmes_hydro"))
    except importlib.metadata.PackageNotFoundError:
        # P1-ERR-03: Use specific exception instead of bare Exception
        return PlainTextResponse("Unknown version", status_code=500)


async def _index(_: Request) -> Response:
    with open(static_dir / "index.html") as f:
        index = f.read()
    return HTMLResponse(index)
