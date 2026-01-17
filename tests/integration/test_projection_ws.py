"""Integration tests for projection WebSocket handler."""

import pytest
from starlette.testclient import TestClient

from holmes.app import create_app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(create_app())


class TestProjectionWebSocket:
    """Tests for projection WebSocket handler."""

    def test_config_message(self, client):
        """Config request returns available projections."""
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            response = ws.receive_json()
            assert response["type"] == "config"
            data = response["data"]
            assert isinstance(data, list)
            if len(data) > 0:
                assert "model" in data[0]
                assert "horizon" in data[0]
                assert "scenario" in data[0]

    def test_projection_run(self, client):
        """Run projection returns results."""
        # First get config to find available model/horizon/scenario
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            config_response = ws.receive_json()
            if len(config_response["data"]) == 0:
                pytest.skip("No projection data available")
            first_config = config_response["data"][0]
            ws.send_json(
                {
                    "type": "projection",
                    "data": {
                        "config": {
                            "model": first_config["model"],
                            "horizon": first_config["horizon"],
                            "scenario": first_config["scenario"],
                        },
                        "calibration": {
                            "catchment": "Au Saumon",
                            "hydroModel": "gr4j",
                            "snowModel": None,
                            "hydroParams": {
                                "x1": 350,
                                "x2": 0.5,
                                "x3": 90,
                                "x4": 1.7,
                            },
                        },
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "projection"
            data = response["data"]
            # Response contains projection (aggregated) and results (metrics)
            assert isinstance(data, dict)
            assert "projection" in data
            assert "results" in data
            assert len(data["projection"]) > 0

    def test_projection_missing_config(self, client):
        """Error for missing config."""
        with client.websocket_connect("/projection/") as ws:
            ws.send_json(
                {
                    "type": "projection",
                    "data": {
                        "calibration": {
                            "catchment": "Au Saumon",
                            "hydroModel": "gr4j",
                            "snowModel": None,
                            "hydroParams": {"x1": 350},
                        }
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"

    def test_unknown_message_type(self, client):
        """Error for unknown type."""
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "unknown_type"})
            response = ws.receive_json()
            assert response["type"] == "error"

    def test_projection_run_with_snow_model(self, client):
        """Run projection with snow model returns results."""
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            config_response = ws.receive_json()
            if len(config_response["data"]) == 0:
                pytest.skip("No projection data available")
            first_config = config_response["data"][0]
            ws.send_json(
                {
                    "type": "projection",
                    "data": {
                        "config": {
                            "model": first_config["model"],
                            "horizon": first_config["horizon"],
                            "scenario": first_config["scenario"],
                        },
                        "calibration": {
                            "catchment": "Au Saumon",
                            "hydroModel": "gr4j",
                            "snowModel": "cemaneige",
                            "hydroParams": {
                                "x1": 350,
                                "x2": 0.5,
                                "x3": 90,
                                "x4": 1.7,
                            },
                        },
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "projection"
            data = response["data"]
            # Response contains projection (aggregated) and results (metrics)
            assert isinstance(data, dict)
            assert "projection" in data
            assert "results" in data
            assert len(data["projection"]) > 0

    def test_projection_on_catchment_without_projection_data_errors(
        self, client
    ):
        """Projection fails on catchment without projection data."""
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Leaf"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Projection" in response["data"] or "not found" in response["data"]
