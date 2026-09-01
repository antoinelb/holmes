import asyncio
import base64
import importlib.metadata
from unittest.mock import AsyncMock, MagicMock

import polars as pl
import pytest
import shapely
from starlette.requests import Request
from starlette.routing import Mount, Route, WebSocketRoute

import holmes.api.api as api
import holmes.api.calibration
import holmes.api.projection
import holmes.api.simulation
import holmes.data.hydro
import holmes.data.weather

black_tile = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def make_request(path_params: dict | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "headers": [],
            "path_params": path_params or {},
        }
    )


async def parked_task() -> asyncio.Task:
    task = asyncio.create_task(asyncio.Event().wait())
    await asyncio.sleep(0)
    return task


class TestGetRoutes:
    def test_route_table(self):
        routes = api.get_routes()
        paths = [
            route.path
            for route in routes
            if isinstance(route, (Route, WebSocketRoute, Mount))
        ]
        assert paths == [
            "/",
            "/version",
            "/static",
            "/ws",
            "/map/{z}/{x}/{y}.png",
        ]


class TestGetVersion:
    async def test_returns_version(self):
        resp = await api._get_version(make_request())
        assert resp.status_code == 200

    async def test_unknown_package_returns_500(self, monkeypatch):
        monkeypatch.setattr(
            api.importlib.metadata,
            "version",
            MagicMock(side_effect=importlib.metadata.PackageNotFoundError),
        )
        resp = await api._get_version(make_request())
        assert resp.status_code == 500


class TestIndex:
    async def test_serves_index_html(self):
        resp = await api._index(make_request())
        assert resp.status_code == 200
        assert b"<!doctype html>" in bytes(resp.body).lower()


class TestGetMapTile:
    async def test_cached_tile_is_served(self, tmp_data_dir):
        path = tmp_data_dir / "map" / "tile_3_1_2.png"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"png")
        resp = await api._get_map_tile(make_request({"x": 1, "y": 2, "z": 3}))
        assert resp.status_code == 200

    async def test_missing_tile_returns_black_pixel(self, tmp_data_dir):
        resp = await api._get_map_tile(make_request({"x": 1, "y": 2, "z": 3}))
        assert resp.body == black_tile
        assert resp.headers["content-type"] == "image/png"


class TestHandleMessage:
    async def test_unknown_type_sends_error(self, fake_ws):
        await api._handle_message(fake_ws, {"type": "bogus"})
        assert fake_ws.sent == [
            {"type": "error", "data": "Unknown message type bogus."}
        ]

    async def test_prints_arrival_line(self, fake_ws, capsys):
        await api._handle_message(fake_ws, {"type": "model_info"})
        assert "Received model_info request." in capsys.readouterr().out

    @pytest.mark.parametrize(
        ["type_", "module", "handler"],
        [
            (
                "calibration_info",
                holmes.api.calibration,
                "handle_calibration_message",
            ),
            (
                "calibration_stop",
                holmes.api.calibration,
                "handle_calibration_message",
            ),
            (
                "simulation_data",
                holmes.api.simulation,
                "handle_simulation_message",
            ),
            (
                "projection_data",
                holmes.api.projection,
                "handle_projection_message",
            ),
        ],
    )
    async def test_dispatches_to_submodules(
        self, monkeypatch, fake_ws, type_, module, handler
    ):
        mock = AsyncMock()
        monkeypatch.setattr(module, handler, mock)
        await api._handle_message(fake_ws, {"type": type_})
        mock.assert_awaited_once()

    async def test_model_info(self, fake_ws):
        await api._handle_message(fake_ws, {"type": "model_info"})
        assert fake_ws.sent[0]["type"] == "model_info"
        assert "gr4j" in fake_ws.sent[0]["data"]["hydro"]


class TestHandleStationsMessage:
    async def test_sends_stations_with_centroids(
        self, monkeypatch, fake_ws, stations_df
    ):
        monkeypatch.setattr(
            holmes.data.hydro,
            "get_station_data",
            MagicMock(return_value=stations_df),
        )
        await api._handle_message(fake_ws, {"type": "stations"})
        reply = fake_ws.sent[0]
        assert reply["type"] == "stations"
        row = reply["data"][0]
        assert "centroid_lat" in row
        # the stored wkb reaches the client as the geojson the map parses
        assert isinstance(row["geometry"], str)
        assert shapely.from_geojson(row["geometry"]).is_valid


class TestForMap:
    def test_geometry_is_the_stored_wkb_as_geojson(self, stations_df):
        data = api._for_map(stations_df)
        stored = shapely.from_wkb(stations_df[0, "geometry"])
        assert shapely.from_geojson(data[0, "geometry"]).equals(stored)

    # archives built before the column was dropped still carry it
    def test_stored_geojson_never_reaches_the_client(self, stations_df):
        legacy = stations_df.with_columns(
            pl.lit("stale geojson").alias("geometry_geojson")
        )
        assert "geometry_geojson" not in api._for_map(legacy).columns

    def test_planar_centroid(self, stations_df):
        data = api._for_map(stations_df)
        row = data.filter(pl.col("id") == "061004").row(0, named=True)
        polygon = shapely.from_geojson(row["geometry"])
        # the projected centroid of a small box stays within metres of the
        # geographic one
        assert row["centroid_lat"] == pytest.approx(
            polygon.centroid.y, abs=1e-3
        )
        assert row["centroid_lon"] == pytest.approx(
            polygon.centroid.x, abs=1e-3
        )


class TestHandleWeatherMessage:
    @pytest.mark.parametrize(
        ["msg", "match"],
        [
            ({"method": "bogus", "stations": []}, "Unknown weather method"),
            ({"method": "era5", "stations": "x"}, "list of station ids"),
            ({"method": "era5", "stations": [1]}, "list of station ids"),
            (
                {"method": "era5", "stations": [], "n_stations": True},
                "Invalid number",
            ),
            (
                {"method": "era5", "stations": [], "n_stations": 6},
                "Invalid number",
            ),
        ],
    )
    async def test_validation_errors(self, fake_ws, msg, match):
        await api._handle_weather_message(fake_ws, msg)
        assert fake_ws.sent[0]["type"] == "error"
        assert match in fake_ws.sent[0]["data"]

    async def test_supersedes_pending_load(self, monkeypatch, fake_ws):
        monkeypatch.setattr(api, "_load_weather", AsyncMock())
        pending = await parked_task()
        fake_ws.state.weather_task = pending
        await api._handle_weather_message(
            fake_ws, {"method": "era5", "stations": ["061004"]}
        )
        assert pending.cancelled() or pending.cancelling()
        await fake_ws.state.weather_task

    async def test_done_task_is_left_alone(self, monkeypatch, fake_ws):
        monkeypatch.setattr(api, "_load_weather", AsyncMock())
        done = asyncio.create_task(asyncio.sleep(0))
        await done
        fake_ws.state.weather_task = done
        await api._handle_weather_message(
            fake_ws, {"method": "era5", "stations": ["061004"]}
        )
        assert not done.cancelled()
        await fake_ws.state.weather_task


class TestLoadWeather:
    async def test_happy_path_echoes_request(
        self, monkeypatch, fake_ws, weather_df, grid_df
    ):
        monkeypatch.setattr(
            holmes.data.weather,
            "read_weather_data",
            lambda **kwargs: weather_df,
        )
        monkeypatch.setattr(
            holmes.data.weather,
            "read_weather_grid",
            lambda **kwargs: grid_df,
        )
        await api._load_weather(fake_ws, "era5", ["061004"], 3)
        reply = fake_ws.sent[0]
        assert reply["type"] == "weather"
        assert reply["data"]["method"] == "era5"
        assert reply["data"]["n_stations"] == 3
        assert all(row["id"] == "061004" for row in reply["data"]["data"])

    async def test_failure_sends_error(self, monkeypatch, fake_ws, capsys):
        monkeypatch.setattr(
            holmes.data.weather,
            "read_weather_data",
            MagicMock(side_effect=RuntimeError("boom")),
        )
        await api._load_weather(fake_ws, "era5", ["061004"], 3)
        assert fake_ws.sent[0]["type"] == "error"
        assert "Failed to load weather data" in fake_ws.sent[0]["data"]
        assert "Failed to load weather data" in capsys.readouterr().out


class TestHandleStreamflowMessage:
    async def test_unknown_station_sends_error(self, fake_ws):
        await api._handle_streamflow_message(fake_ws, {"station": "999"})
        assert fake_ws.sent[0]["type"] == "error"

    async def test_tracks_independent_tasks(self, monkeypatch, fake_ws):
        monkeypatch.setattr(api, "_load_streamflow", AsyncMock())
        await api._handle_streamflow_message(fake_ws, {"station": "061004"})
        await api._handle_streamflow_message(fake_ws, {"station": "061020"})
        await asyncio.sleep(0.01)
        assert len(fake_ws.state.tasks) == 0  # both completed, discarded


class TestLoadStreamflow:
    async def test_happy_path_echoes_station(
        self, monkeypatch, fake_ws, streamflow_df
    ):
        monkeypatch.setattr(
            holmes.data.hydro,
            "get_streamflow_data",
            MagicMock(
                return_value=streamflow_df.filter(pl.col("id") == "061004")
            ),
        )
        await api._load_streamflow(fake_ws, "061004")
        reply = fake_ws.sent[0]
        assert reply["type"] == "streamflow"
        assert reply["data"]["station"] == "061004"

    async def test_failure_sends_error(self, monkeypatch, fake_ws, capsys):
        monkeypatch.setattr(
            holmes.data.hydro,
            "get_streamflow_data",
            MagicMock(side_effect=RuntimeError("boom")),
        )
        await api._load_streamflow(fake_ws, "061004")
        assert fake_ws.sent[0]["type"] == "error"
        assert "Failed to load streamflow data" in capsys.readouterr().out


class TestCleanupWebsocket:
    async def test_no_state_is_fine(self, fake_ws):
        await api._cleanup_websocket(fake_ws)

    async def test_cancels_pending_tasks(self, fake_ws):
        pending = await parked_task()
        done = asyncio.create_task(asyncio.sleep(0))
        await done
        fake_ws.state.tasks = {pending, done}
        await api._cleanup_websocket(fake_ws)
        assert pending.cancelled()
        assert fake_ws.state.tasks == set()

    async def test_stubborn_task_times_out(self, fake_ws):
        async def stubborn():
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await asyncio.sleep(5)

        task = asyncio.create_task(stubborn())
        await asyncio.sleep(0)
        fake_ws.state.tasks = {task}
        await api._cleanup_websocket(fake_ws)
        assert fake_ws.state.tasks == set()
        task.cancel()

    async def test_clears_stop_event_and_stops(self, fake_ws):
        import threading

        fake_ws.state.stop_event = object()
        stop = threading.Event()
        fake_ws.state.calibration_stops = {"gr4j": stop}
        await api._cleanup_websocket(fake_ws)
        assert not hasattr(fake_ws.state, "stop_event")
        assert stop.is_set()
