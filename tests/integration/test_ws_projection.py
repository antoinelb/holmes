import holmes_rs

import holmes.data.projection

from tests.integration.conftest import recv_until

gr4j_defaults = list(holmes_rs.hydro.gr4j.init()[0])


def projection_message(**overrides) -> dict:
    msg = {
        "type": "projection_data",
        "station": "061004",
        "start": "2016-01-01",
        "end": "2017-12-31",
        "method": "ministry_grid",
        "hydroModels": ["gr4j"],
        "snowModel": "none",
        "climateModel": "ClimEx",
        "scenario": "rcp8.5",
        "horizon": "2020-2049",
        "requestId": 1,
        "warmupYears": 1,
        "n_stations": 3,
        "hydroParams": {"gr4j": gr4j_defaults},
    }
    msg.update(overrides)
    return msg


class TestProjection:
    def test_runs_the_ensemble(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(projection_message())
            msg = recv_until(ws, "projection_result")
            data = msg["data"]
            assert data["requestId"] == 1
            assert data["climateModel"] == "ClimEx"
            assert data["memberCounts"] == {"rcp8.5": 2}
            members = data["results"]["gr4j"]["members"]
            assert len(members) == 2
            for member in members.values():
                assert len(member["regime"]) == 365
                assert member["indicators"]["mean"] is not None
            assert len(data["median"]["regime"]) == 365
            assert len(data["historical"]["regime"]) == 365

    def test_second_request_reuses_cached_simulations(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(projection_message(requestId=1))
            recv_until(ws, "projection_result")
            ws.send_json(projection_message(requestId=2, horizon="2040-2069"))
            msg = recv_until(ws, "projection_result")
            assert msg["data"]["requestId"] == 2
            assert msg["data"]["horizon"] == "2040-2069"

    def test_missing_products_refuse(self, client, monkeypatch):
        monkeypatch.setattr(
            holmes.data.projection,
            "has_projection_data",
            lambda stations: False,
        )
        with client.websocket_connect("/ws") as ws:
            ws.send_json(projection_message(requestId=3))
            msg = recv_until(ws, "projection_error")
            assert "holmes download" in msg["data"]["message"]
