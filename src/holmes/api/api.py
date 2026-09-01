import asyncio
import base64
import importlib.metadata
from typing import Any, cast, get_args

import geopandas as gpd
import polars as pl
import shapely
from starlette.requests import Request
from starlette.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    Response,
)
from starlette.routing import BaseRoute, Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

import holmes.data.hydro
import holmes.data.weather
from holmes.api import calibration, projection, simulation
from holmes.api.utils import send as _send
from holmes.api.utils import with_path_params
from holmes.model_info import get_model_info
from holmes.utils.paths import data_dir, static_dir
from holmes.utils.print import done_print, fail_print, warn_print

##########
# public #
##########


def get_routes() -> list[BaseRoute]:
    return [
        Route("/", endpoint=_index, methods=["GET"]),
        Route("/version", endpoint=_get_version, methods=["GET"]),
        Mount(
            "/static",
            app=StaticFiles(directory=str(static_dir.absolute())),
        ),
        WebSocketRoute("/ws", endpoint=_websocket),
        Route(
            "/map/{z}/{x}/{y}.png",
            endpoint=_get_map_tile,
            methods=["GET"],
        ),
    ]


##########
# routes #
##########


async def _get_version(_: Request) -> Response:
    try:
        return PlainTextResponse(importlib.metadata.version("holmes-hydro"))
    except importlib.metadata.PackageNotFoundError:
        return PlainTextResponse("Unknown version", status_code=500)


async def _index(_: Request) -> Response:
    with open(static_dir / "index.html") as f:
        index = f.read()
    return HTMLResponse(index)


async def _websocket(ws: WebSocket) -> None:
    await ws.accept()
    done_print("WebSocket client connected.")
    try:
        while True:
            msg = await ws.receive_json()
            await _handle_message(ws, msg)
    except WebSocketDisconnect:
        warn_print("WebSocket client disconnected.")
    finally:
        await _cleanup_websocket(ws)


@with_path_params(args=["x", "y", "z"])
async def _get_map_tile(_: Request, x: int, y: int, z: int) -> Response:
    # read-only: the tiles ship in the data archive (Carto needs an API
    # key now, so the server can no longer fetch them lazily)
    path = data_dir / "map" / f"tile_{z}_{x}_{y}.png"
    if path.exists():
        return FileResponse(str(path))
    # return a black tile if the tile isn't available
    else:
        return Response(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            ),
            media_type="image/png",
        )


###########
# private #
###########


async def _handle_message(ws: WebSocket, msg: dict[str, Any]) -> None:
    msg_type = msg.get("type")
    done_print(f"Received {msg_type} request.")

    match msg_type:
        case "stations":
            await _handle_stations_message(ws)
        case "weather":
            await _handle_weather_message(ws, msg)
        case "streamflow":
            await _handle_streamflow_message(ws, msg)
        case "model_info":
            await _handle_model_info_message(ws)
        case (
            "calibration_info"
            | "calibration_data"
            | "calibration_manual"
            | "calibration_start"
            | "calibration_stop"
        ):
            await calibration.handle_calibration_message(ws, msg)
        case "simulation_data":
            await simulation.handle_simulation_message(ws, msg)
        case "projection_data":
            await projection.handle_projection_message(ws, msg)
        case _:
            await _send(ws, "error", f"Unknown message type {msg_type}.")


async def _handle_stations_message(ws: WebSocket) -> None:
    # a task, like streamflow's: this reply is by far the largest, and the
    # receive loop must read the requests queued behind it rather than hold
    # them until it is written
    _track(ws, asyncio.create_task(_load_stations(ws)))


async def _load_stations(ws: WebSocket) -> None:
    try:
        # the read and the wkb -> geojson pass both stay off the event loop
        data = await asyncio.to_thread(
            lambda: _for_map(holmes.data.hydro.get_station_data())
        )
    except Exception as exc:
        message = f"Failed to load station data: {exc}"
        fail_print(message)
        await _send(ws, "error", message)
        return

    await _send(ws, "stations", data)


def _track(ws: WebSocket, task: asyncio.Task[None]) -> None:
    """Register a load task so `_cleanup_websocket` can cancel it."""
    if not hasattr(ws.state, "tasks"):
        ws.state.tasks = set()
    ws.state.tasks.add(task)
    task.add_done_callback(ws.state.tasks.discard)


def _for_map(data: pl.DataFrame) -> pl.DataFrame:
    """Watershed outlines and centroids, both derived from the stored wkb.

    Centroids are the planar EPSG:32198 centroid — the same point the
    nearest-stations selection measures distances to — so the markers and
    link lines anchor exactly where the picks were ranked from.
    The geojson the map draws is derived here rather than stored: one
    parse of the wkb serves both, and the archive carries one copy of
    every polygon instead of two. Archives built before that still carry
    the stored copy, dropped here so it never reaches the client.
    """
    shapes = gpd.GeoSeries(
        [shapely.from_wkb(geometry) for geometry in data["geometry"]],
        crs="EPSG:4326",
    )
    centroids = shapes.to_crs("EPSG:32198").centroid.to_crs("EPSG:4326")
    return data.drop("geometry_geojson", strict=False).with_columns(
        pl.Series("geometry", [shapely.to_geojson(shape) for shape in shapes]),
        pl.Series("centroid_lat", [point.y for point in centroids]),
        pl.Series("centroid_lon", [point.x for point in centroids]),
    )


async def _handle_weather_message(ws: WebSocket, msg: dict[str, Any]) -> None:
    method = msg.get("method")
    stations = msg.get("stations")
    # absent on messages from a tab predating the field, so it defaults
    n_stations = msg.get("n_stations", 3)

    if method not in get_args(holmes.data.weather.WeatherMethod):
        await _send(ws, "error", f"Unknown weather method {method}.")
        return
    if not isinstance(stations, list) or not all(
        isinstance(station, str) for station in stations
    ):
        await _send(
            ws, "error", "Weather message needs a list of station ids."
        )
        return
    # `type is int` rather than isinstance: booleans are int subclasses
    if type(n_stations) is not int or not (
        holmes.data.weather.min_n_stations
        <= n_stations
        <= holmes.data.weather.max_n_stations
    ):
        await _send(
            ws, "error", f"Invalid number of nearest stations {n_stations}."
        )
        return
    # a new pick supersedes any pending load
    previous = getattr(ws.state, "weather_task", None)
    if previous is not None and not previous.done():
        previous.cancel()

    task = asyncio.create_task(
        _load_weather(
            ws,
            cast(holmes.data.weather.WeatherMethod, method),
            stations,
            n_stations,
        )
    )
    ws.state.weather_task = task
    _track(ws, task)


async def _load_weather(
    ws: WebSocket,
    method: holmes.data.weather.WeatherMethod,
    stations: list[str],
    n_stations: int,
) -> None:
    try:
        # sync IPC reads of prebuilt products, kept off the event loop
        weather = await asyncio.to_thread(
            holmes.data.weather.read_weather_data,
            method=method,
            n_stations=n_stations,
        )
        # the grid is n-independent (nearest_stations always sends the full
        # station pool), so only the data read takes the count
        grid = await asyncio.to_thread(
            holmes.data.weather.read_weather_grid,
            method=method,
        )
    except Exception as exc:
        message = f"Failed to load weather data: {exc}"
        fail_print(message)
        await _send(ws, "error", message)
        return

    data = weather.filter(pl.col("id").is_in(stations)).with_columns(
        pl.col("datetime").dt.date()
    )
    # echo the request fields so a late reply for a superseded pick is
    # identifiable
    await _send(
        ws,
        "weather",
        {
            "method": method,
            "n_stations": n_stations,
            "data": data,
            "grid": grid.filter(pl.col("id").is_in(stations)),
        },
    )


async def _handle_streamflow_message(
    ws: WebSocket, msg: dict[str, Any]
) -> None:
    station = msg.get("station")

    if station not in holmes.data.hydro.STATIONS:
        await _send(ws, "error", f"Unknown station {station}.")
        return

    # unlike weather, requests are independent (one per role) and cheap, so
    # none supersedes another
    _track(ws, asyncio.create_task(_load_streamflow(ws, station)))


async def _load_streamflow(ws: WebSocket, station: str) -> None:
    try:
        data = await asyncio.to_thread(
            holmes.data.hydro.get_streamflow_data, station
        )
    except Exception as exc:
        message = f"Failed to load streamflow data: {exc}"
        fail_print(message)
        await _send(ws, "error", message)
        return

    # echo the station so the client can key its cache without inspecting
    # rows
    await _send(ws, "streamflow", {"station": station, "data": data})


async def _handle_model_info_message(ws: WebSocket) -> None:
    # descriptions are static and instant, so no task tracking is needed
    await _send(ws, "model_info", get_model_info())


async def _cleanup_websocket(ws: WebSocket) -> None:
    # cancelling an asyncio.to_thread task does not stop its worker thread; the
    # stop events are what actually terminate the running SCE loops, so set them
    # before awaiting the task cancellations below
    calibration.cleanup_calibration(ws)

    # cancel any pending tasks
    if hasattr(ws.state, "tasks"):
        for task in list(ws.state.tasks):
            if not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=1.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
        ws.state.tasks.clear()

    if hasattr(ws.state, "stop_event"):
        delattr(ws.state, "stop_event")

    done_print("WebSocket cleanup completed")
