"""Unit tests for holmes.api.simulation module."""

from unittest.mock import patch

import polars as pl
from starlette.testclient import TestClient

from holmes.app import create_app


class TestSimulationWebSocket:
    """Tests for simulation WebSocket handler."""

    def test_get_routes(self):
        """get_routes returns WebSocket routes."""
        from starlette.routing import WebSocketRoute

        from holmes.api.simulation import get_routes

        routes = get_routes()
        assert len(routes) == 1
        route = routes[0]
        assert isinstance(route, WebSocketRoute)
        assert route.path == "/"

    def test_websocket_config_message(self):
        """Config message returns date range for catchment."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            response = ws.receive_json()
            assert response["type"] == "config"
            assert "start" in response["data"]
            assert "end" in response["data"]

    def test_websocket_config_unknown_catchment(self):
        """Config message with unknown catchment returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json({"type": "config", "data": "Unknown Catchment"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Unknown catchment" in response["data"]

    def test_websocket_config_missing_data(self):
        """Config message without data sends error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json({"type": "config"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "catchment must be provided" in response["data"]

    def test_websocket_observations_message(self):
        """Observations message returns streamflow data."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "observations",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2000-12-31",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "observations"
            assert isinstance(response["data"], list)

    def test_websocket_observations_missing_params(self):
        """Observations without required params returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json({"type": "observations", "data": {}})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "must be provided" in response["data"]

    def test_websocket_simulation_message(self):
        """Simulation message returns streamflow simulation."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "2000-01-01",
                            "end": "2000-12-31",
                            "multimodel": False,
                        },
                        "calibration": [
                            {
                                "catchment": "Au Saumon",
                                "hydroModel": "gr4j",
                                "snowModel": "cemaneige",
                                "hydroParams": {
                                    "x1": 100.0,
                                    "x2": 0.0,
                                    "x3": 50.0,
                                    "x4": 2.0,
                                },
                            },
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "simulation"
            assert "simulation" in response["data"]
            assert "results" in response["data"]

    def test_websocket_simulation_without_snow(self):
        """Simulation works without snow model."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "2000-01-01",
                            "end": "2000-12-31",
                            "multimodel": False,
                        },
                        "calibration": [
                            {
                                "catchment": "Au Saumon",
                                "hydroModel": "bucket",
                                "snowModel": None,
                                "hydroParams": {
                                    "c_soil": 100.0,
                                    "alpha": 0.5,
                                    "k_r": 100.0,
                                    "delta": 6.0,
                                    "beta": 0.5,
                                    "k_t": 200.0,
                                },
                            },
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "simulation"

    def test_websocket_simulation_multimodel(self):
        """Simulation with multimodel averages simulations."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "2000-01-01",
                            "end": "2000-12-31",
                            "multimodel": True,
                        },
                        "calibration": [
                            {
                                "catchment": "Au Saumon",
                                "hydroModel": "gr4j",
                                "snowModel": "cemaneige",
                                "hydroParams": {
                                    "x1": 100.0,
                                    "x2": 0.0,
                                    "x3": 50.0,
                                    "x4": 2.0,
                                },
                            },
                            {
                                "catchment": "Au Saumon",
                                "hydroModel": "bucket",
                                "snowModel": "cemaneige",
                                "hydroParams": {
                                    "c_soil": 100.0,
                                    "alpha": 0.5,
                                    "k_r": 100.0,
                                    "delta": 6.0,
                                    "beta": 0.5,
                                    "k_t": 200.0,
                                },
                            },
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "simulation"
            # Should have multimodel result
            results = response["data"]["results"]
            names = [r["name"] for r in results]
            assert "multimodel" in names

    def test_websocket_simulation_missing_params(self):
        """Simulation without required params returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json({"type": "simulation", "data": {}})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "must be provided" in response["data"]

    def test_websocket_simulation_empty_calibration(self):
        """Simulation with empty calibration list returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "2000-01-01",
                            "end": "2000-12-31",
                            "multimodel": False,
                        },
                        "calibration": [],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert (
                "At least one calibration config must be provided"
                in response["data"]
            )

    def test_websocket_simulation_missing_dates(self):
        """Simulation without start/end dates returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": None,
                            "end": None,
                            "multimodel": False,
                        },
                        "calibration": [
                            {
                                "catchment": "Au Saumon",
                                "hydroModel": "gr4j",
                                "snowModel": None,
                                "hydroParams": {
                                    "x1": 100,
                                    "x2": 0,
                                    "x3": 50,
                                    "x4": 2,
                                },
                            },
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "start" in response["data"] or "end" in response["data"]

    def test_websocket_unknown_message_type(self):
        """Unknown message type returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json({"type": "unknown_type"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Unknown message type" in response["data"]


class TestSimulationDataErrors:
    """Tests for HolmesDataError handling in simulation API."""

    def test_observations_invalid_catchment(self):
        """Observations with invalid catchment returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "observations",
                    "data": {
                        "catchment": "NonExistentCatchment",
                        "start": "2000-01-01",
                        "end": "2000-12-31",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "catchment" in response["data"].lower()

    def test_simulation_invalid_catchment(self):
        """Simulation with invalid catchment returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/simulation/") as ws:
            ws.send_json(
                {
                    "type": "simulation",
                    "data": {
                        "config": {
                            "start": "2000-01-01",
                            "end": "2000-12-31",
                            "multimodel": False,
                        },
                        "calibration": [
                            {
                                "catchment": "NonExistentCatchment",
                                "hydroModel": "gr4j",
                                "snowModel": None,
                                "hydroParams": {
                                    "x1": 100.0,
                                    "x2": 0.0,
                                    "x3": 50.0,
                                    "x4": 2.0,
                                },
                            },
                        ],
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "catchment" in response["data"].lower()

    def test_simulation_with_snow_model_missing_temperature(self):
        """Simulation with snow model fails when temperature data is missing."""
        # Create mock data without temperature column
        mock_data = pl.DataFrame(
            {
                "date": pl.date_range(
                    pl.date(2000, 1, 1), pl.date(2000, 12, 31), eager=True
                ),
                "precipitation": [1.0] * 366,
                "pet": [2.0] * 366,
                "streamflow": [0.5] * 366,
            }
        )

        mock_cemaneige = {
            "qnbv": 1.0,
            "altitude_layers": [500.0, 1000.0],
            "median_altitude": 750.0,
            "latitude": 45.0,
        }

        with (
            patch("holmes.api.simulation.data.read_data", return_value=mock_data),
            patch(
                "holmes.api.simulation.data.read_cemaneige_info",
                return_value=mock_cemaneige,
            ),
        ):
            client = TestClient(create_app())
            with client.websocket_connect("/simulation/") as ws:
                ws.send_json(
                    {
                        "type": "simulation",
                        "data": {
                            "config": {
                                "start": "2000-01-01",
                                "end": "2000-12-31",
                                "multimodel": False,
                            },
                            "calibration": [
                                {
                                    "catchment": "MockCatchment",
                                    "hydroModel": "gr4j",
                                    "snowModel": "cemaneige",
                                    "hydroParams": {
                                        "x1": 100.0,
                                        "x2": 0.0,
                                        "x3": 50.0,
                                        "x4": 2.0,
                                    },
                                },
                            ],
                        },
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "temperature" in response["data"].lower()
