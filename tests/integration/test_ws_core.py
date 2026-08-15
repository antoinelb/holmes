import threading

import holmes.data.weather

from tests.integration.conftest import recv_until


class TestStations:
    def test_sends_stations_with_centroids(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "stations"})
            msg = recv_until(ws, "stations")
            row = msg["data"][0]
            assert row["id"] in ["061004", "061020"]
            assert "centroid_lat" in row
            assert isinstance(row["geometry"], str)


class TestWeather:
    def test_happy_path_echoes_request(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "type": "weather",
                    "method": "ministry_grid",
                    "stations": ["061004"],
                }
            )
            msg = recv_until(ws, "weather")
            assert msg["data"]["method"] == "ministry_grid"
            assert msg["data"]["n_stations"] == 3
            assert {row["id"] for row in msg["data"]["data"]} == {"061004"}
            assert {row["id"] for row in msg["data"]["grid"]} == {"061004"}

    def test_new_pick_supersedes_pending_load(
        self, client, monkeypatch, weather_df
    ):
        release = threading.Event()
        calls = {"count": 0}

        def gated_read_weather_data(**kwargs):
            # runs in the api's to_thread worker, so a plain wait parks the
            # first load on a thread-safe gate the test opens after the
            # second request has superseded it
            calls["count"] += 1
            if calls["count"] == 1:
                release.wait()
            return weather_df

        monkeypatch.setattr(
            holmes.data.weather,
            "read_weather_data",
            gated_read_weather_data,
        )
        try:
            with client.websocket_connect("/ws") as ws:
                ws.send_json(
                    {
                        "type": "weather",
                        "method": "era5",
                        "stations": ["061004"],
                    }
                )
                ws.send_json(
                    {
                        "type": "weather",
                        "method": "ministry_grid",
                        "stations": ["061004"],
                    }
                )
                release.set()
                msg = recv_until(ws, "weather")
                # the only reply is the superseding request's
                assert msg["data"]["method"] == "ministry_grid"
                # a follow-up proves no stale weather frame is queued behind
                ws.send_json({"type": "model_info"})
                assert ws.receive_json()["type"] == "model_info"
        finally:
            release.set()


class TestStreamflow:
    def test_happy_path_echoes_station(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "streamflow", "station": "061004"})
            msg = recv_until(ws, "streamflow")
            assert msg["data"]["station"] == "061004"
            assert len(msg["data"]["data"]) > 0


class TestModelInfo:
    def test_serves_descriptions(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "model_info"})
            msg = recv_until(ws, "model_info")
            assert "gr4j" in msg["data"]["hydro"]


class TestUnknownMessage:
    def test_sends_error(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "bogus"})
            msg = recv_until(ws, "error")
            assert "Unknown message type" in msg["data"]
