import importlib.metadata
import re
from functools import lru_cache

from holmes.utils.paths import static_dir
from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse, Response
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles

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
        Route(
            "/static/styles/{path:path}", endpoint=_serve_css, methods=["GET"]
        ),
        Route(
            "/static/scripts/{path:path}", endpoint=_serve_js, methods=["GET"]
        ),
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

    version = _get_app_version()
    index = re.sub(
        r'(href|src)="(/static/[^"]+)"', rf'\1="\2?v={version}"', index
    )

    return HTMLResponse(index)


async def _serve_css(request: Request) -> Response:
    path = request.path_params["path"]
    version = _get_app_version()

    try:
        css = _get_versioned_css(path, version)
    except FileNotFoundError:
        return PlainTextResponse("Not found", status_code=404)

    return Response(css, media_type="text/css")


async def _serve_js(request: Request) -> Response:
    """Serve JS files with versioned import URLs."""
    path = request.path_params["path"]
    version = _get_app_version()

    try:
        js = _get_versioned_js(path, version)
    except FileNotFoundError:
        return PlainTextResponse("Not found", status_code=404)

    return Response(js, media_type="application/javascript")


def _get_app_version() -> str:
    try:
        return importlib.metadata.version("holmes-hydro")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


@lru_cache
def _get_versioned_css(path: str, version: str) -> str:
    file_path = static_dir / "styles" / path
    if not file_path.is_file():
        raise FileNotFoundError(path)

    css = file_path.read_text()
    pattern = r'@import\s+"([^"]+)"'
    replacement = rf'@import "\1?v={version}"'
    return re.sub(pattern, replacement, css)


@lru_cache
def _get_versioned_js(path: str, version: str) -> str:
    file_path = static_dir / "scripts" / path
    if not file_path.is_file():
        raise FileNotFoundError(path)

    js = file_path.read_text()
    pattern = r'(from\s+["\'])([^"\']+)(["\'])'
    replacement = rf"\1\2?v={version}\3"
    return re.sub(pattern, replacement, js)
