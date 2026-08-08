import asyncio
import threading

import holmes_rs

import holmes.experiment

from tests.integration.conftest import recv_until

gr4j_defaults = list(holmes_rs.hydro.gr4j.init()[0])
bucket_defaults = list(holmes_rs.hydro.bucket.init()[0])


def simulation_message(**overrides) -> dict:
    msg = {
        "type": "simulation_data",
        "station": "061004",
        "method": "ministry_grid",
        "start": "2016-01-01",
        "end": "2016-12-31",
        "hydroModels": ["gr4j", "bucket"],
        "snowModel": "none",
        "requestId": 1,
        "warmupYears": 1,
        "n_stations": 3,
        "hydroParams": {"gr4j": gr4j_defaults, "bucket": bucket_defaults},
    }
    msg.update(overrides)
    return msg


class TestSimulation:
    def test_simulates_models_and_median(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(simulation_message())
            msg = recv_until(ws, "simulation_result")
            data = msg["data"]
            assert data["requestId"] == 1
            assert data["station"] == "061004"
            assert set(data["results"]) == {"gr4j", "bucket"}
            for result in data["results"].values():
                assert len(result["simulation"]) == 366 + 365
                assert result["metrics"]["kge"] is not None
            assert len(data["median"]["simulation"]) == 366 + 365

    def test_with_snow(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                simulation_message(
                    hydroModels=["gr4j"],
                    hydroParams={"gr4j": gr4j_defaults},
                    snowModel="cemaneige",
                    snowParams=[0.25, 3.74, 300.0],
                    requestId=2,
                )
            )
            msg = recv_until(ws, "simulation_result")
            assert msg["data"]["requestId"] == 2

    def test_new_request_supersedes_pending_one(
        self, client, monkeypatch, joined_df
    ):
        release = threading.Event()

        async def gated_read_data(**kwargs):
            await asyncio.to_thread(release.wait)
            return joined_df

        monkeypatch.setattr(holmes.experiment, "read_data", gated_read_data)
        try:
            with client.websocket_connect("/ws") as ws:
                ws.send_json(simulation_message(requestId=1))
                ws.send_json(simulation_message(requestId=2))
                release.set()
                msg = recv_until(ws, "simulation_result")
                assert msg["data"]["requestId"] == 2
                ws.send_json({"type": "model_info"})
                assert ws.receive_json()["type"] == "model_info"
        finally:
            release.set()
