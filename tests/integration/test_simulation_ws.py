"""Integration tests for simulation WebSocket handler."""

import pytest
from starlette.testclient import TestClient

from holmes.app import create_app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(create_app())


class TestSimulationWebSocket:
    """Tests for simulation WebSocket handler."""

    def test_config_message(self, client):
        """Config request returns expected structure."""
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            response = ws.receive_json()
            assert response["type"] == "config"
            data = response["data"]
            assert "start" in data
            assert "end" in data

    def test_observations_message(self, client):
        """Load observations returns data."""
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "observations",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2001-12-31",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "observations"
            assert isinstance(response["data"], list)
            assert len(response["data"]) > 0

    def test_simulation_run(self, client):
        """Run simulation returns results."""
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "2000-01-01",
                            "end": "2001-12-31",
                            "multimodel": False,
                        },
                        "calibration": [
                            {
                                "catchment": "Au Saumon",
                                "hydroModel": "gr4j",
                                "snowModel": None,
                                "hydroParams": {
                                    "x1": 350,
                                    "x2": 0.5,
                                    "x3": 90,
                                    "x4": 1.7,
                                },
                            }
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "simulation"
            data = response["data"]
            assert "simulation" in data
            assert "results" in data

    def test_simulation_with_multimodel(self, client):
        """Run simulation with multimodel option using GR4J with different params."""
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "2000-01-01",
                            "end": "2001-12-31",
                            "multimodel": True,
                        },
                        "calibration": [
                            {
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
                            {
                                "catchment": "Au Saumon",
                                "hydroModel": "gr4j",
                                "snowModel": None,
                                "hydroParams": {
                                    "x1": 400,
                                    "x2": 0.3,
                                    "x3": 100,
                                    "x4": 2.0,
                                },
                            },
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "simulation"
            data = response["data"]
            assert "simulation" in data
            assert "results" in data
            # Should have multimodel result
            result_names = [r["name"] for r in data["results"]]
            assert "multimodel" in result_names

    def test_simulation_missing_config(self, client):
        """Error for missing config."""
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "calibration": [
                            {
                                "catchment": "Au Saumon",
                                "hydroModel": "gr4j",
                                "snowModel": None,
                                "hydroParams": {"x1": 350},
                            }
                        ]
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"

    def test_unknown_message_type(self, client):
        """Error for unknown type."""
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json({"type": "unknown_type"})
            response = ws.receive_json()
            assert response["type"] == "error"

    def test_simulation_without_snow_model_on_catchment_without_cemaneige(
        self, client
    ):
        """Simulation without snow model works on catchment without CemaNeige info."""
        # Leaf catchment data is from 1957-1987, use dates within that range
        # (with 3 years warmup, start from 1960)
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "1980-01-01",
                            "end": "1981-12-31",
                            "multimodel": False,
                        },
                        "calibration": [
                            {
                                "catchment": "Leaf",
                                "hydroModel": "gr4j",
                                "snowModel": None,
                                "hydroParams": {
                                    "x1": 350,
                                    "x2": 0.5,
                                    "x3": 90,
                                    "x4": 1.7,
                                },
                            }
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "simulation"
            data = response["data"]
            assert "simulation" in data
            assert "results" in data

    def test_simulation_with_snow_model_on_catchment_without_cemaneige_errors(
        self, client
    ):
        """Simulation with snow model fails on catchment without CemaNeige info."""
        # Leaf catchment has no CemaNeige info file
        # Leaf catchment data is from 1957-1987
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "1980-01-01",
                            "end": "1981-12-31",
                            "multimodel": False,
                        },
                        "calibration": [
                            {
                                "catchment": "Leaf",
                                "hydroModel": "gr4j",
                                "snowModel": "cemaneige",
                                "hydroParams": {
                                    "x1": 350,
                                    "x2": 0.5,
                                    "x3": 90,
                                    "x4": 1.7,
                                },
                            }
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "CemaNeige" in response["data"]
