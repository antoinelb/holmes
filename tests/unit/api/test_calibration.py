"""Unit tests for holmes.api.calibration module."""

from unittest.mock import patch

import polars as pl
from starlette.testclient import TestClient

from holmes.app import create_app
from holmes.exceptions import HolmesDataError


class TestCalibrationWebSocket:
    """Tests for calibration WebSocket handler."""

    def test_get_routes(self):
        """get_routes returns WebSocket routes."""
        from starlette.routing import WebSocketRoute

        from holmes.api.calibration import get_routes

        routes = get_routes()
        assert len(routes) == 1
        route = routes[0]
        assert isinstance(route, WebSocketRoute)
        assert route.path == "/"

    def test_websocket_config_message(self):
        """Config message returns catchments and model options."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json({"type": "config"})
            response = ws.receive_json()
            assert response["type"] == "config"
            assert "hydro_model" in response["data"]
            assert "catchment" in response["data"]
            assert "snow_model" in response["data"]
            assert "objective" in response["data"]
            assert "transformation" in response["data"]
            assert "algorithm" in response["data"]

    def test_websocket_observations_message(self):
        """Observations message returns streamflow data."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
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
            assert "data" in response
            # Should be list of records
            assert isinstance(response["data"], list)

    def test_websocket_observations_missing_params(self):
        """Observations without required params returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json({"type": "observations", "data": {}})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "must be provided" in response["data"]

    def test_websocket_manual_calibration(self):
        """Manual calibration returns simulation results."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "manual",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2000-12-31",
                        "hydroModel": "gr4j",
                        "snowModel": "cemaneige",
                        "hydroParams": [100.0, 0.0, 50.0, 2.0],
                        "objective": "nse",
                        "transformation": "none",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "result"
            assert response["data"]["done"] is True
            assert "simulation" in response["data"]
            assert "params" in response["data"]
            assert "objective" in response["data"]

    def test_websocket_manual_calibration_without_snow(self):
        """Manual calibration works without snow model."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "manual",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2000-12-31",
                        "hydroModel": "bucket",
                        "snowModel": None,
                        "hydroParams": [100.0, 0.5, 100.0, 6.0, 0.5, 200.0],
                        "objective": "rmse",
                        "transformation": "sqrt",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "result"
            assert response["data"]["done"] is True

    def test_websocket_manual_calibration_missing_params(self):
        """Manual calibration without required params returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json({"type": "manual", "data": {}})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "must be provided" in response["data"]

    def test_websocket_unknown_message_type(self):
        """Unknown message type returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json({"type": "unknown_type"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Unknown message type" in response["data"]

    def test_websocket_calibration_start(self):
        """Calibration start initiates calibration and returns results."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "calibration_start",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2000-06-30",
                        "hydroModel": "gr4j",
                        "snowModel": "cemaneige",
                        "objective": "nse",
                        "transformation": "none",
                        "algorithm": "sce",
                        "algorithmParams": {
                            "n_complexes": 2,
                            "k_stop": 3,
                            "p_convergence_threshold": 0.1,
                            "geometric_range_threshold": 0.001,
                            "max_evaluations": 50,
                        },
                    },
                }
            )
            # Should receive at least one result message
            response = ws.receive_json()
            assert response["type"] == "result"
            assert "simulation" in response["data"]

    def test_websocket_calibration_start_missing_params(self):
        """Calibration start without required params returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json({"type": "calibration_start", "data": {}})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "must be provided" in response["data"]

    def test_websocket_calibration_stop(self):
        """Calibration stop sets stop event."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            # Start calibration
            ws.send_json(
                {
                    "type": "calibration_start",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2000-06-30",
                        "hydroModel": "gr4j",
                        "snowModel": "cemaneige",
                        "objective": "nse",
                        "transformation": "none",
                        "algorithm": "sce",
                        "algorithmParams": {
                            "n_complexes": 2,
                            "k_stop": 2,
                            "p_convergence_threshold": 0.1,
                            "geometric_range_threshold": 0.001,
                            "max_evaluations": 1000,
                        },
                    },
                }
            )
            # Immediately send stop
            ws.send_json({"type": "calibration_stop"})
            # Should receive some results
            response = ws.receive_json()
            assert response["type"] == "result"

    def test_websocket_calibration_stop_without_start(self):
        """Calibration stop without prior start is handled gracefully."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            # Send stop without start - should not raise error
            ws.send_json({"type": "calibration_stop"})
            # Send config to verify connection still works
            ws.send_json({"type": "config"})
            response = ws.receive_json()
            assert response["type"] == "config"


class TestCalibrationDataErrors:
    """Tests for HolmesDataError handling in calibration API."""

    def test_observations_invalid_catchment(self):
        """Observations with invalid catchment returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
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

    def test_observations_invalid_date_format(self):
        """Observations with invalid date format returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "observations",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000/01/01",  # Wrong format
                        "end": "2000-12-31",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "date" in response["data"].lower()

    def test_manual_calibration_invalid_catchment(self):
        """Manual calibration with invalid catchment returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "manual",
                    "data": {
                        "catchment": "NonExistentCatchment",
                        "start": "2000-01-01",
                        "end": "2000-12-31",
                        "hydroModel": "gr4j",
                        "snowModel": None,
                        "hydroParams": [100.0, 0.0, 50.0, 2.0],
                        "objective": "nse",
                        "transformation": "none",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "catchment" in response["data"].lower()

    def test_calibration_start_invalid_catchment(self):
        """Calibration start with invalid catchment returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "calibration_start",
                    "data": {
                        "catchment": "NonExistentCatchment",
                        "start": "2000-01-01",
                        "end": "2000-06-30",
                        "hydroModel": "gr4j",
                        "snowModel": None,
                        "objective": "nse",
                        "transformation": "none",
                        "algorithm": "sce",
                        "algorithmParams": {
                            "n_complexes": 2,
                            "k_stop": 3,
                            "p_convergence_threshold": 0.1,
                            "geometric_range_threshold": 0.001,
                            "max_evaluations": 50,
                        },
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "catchment" in response["data"].lower()

    def test_manual_calibration_with_snow_model_invalid_cemaneige_info(self):
        """Manual calibration with snow model fails when cemaneige info is invalid."""
        mock_data = pl.DataFrame(
            {
                "date": pl.date_range(
                    pl.date(2000, 1, 1), pl.date(2000, 12, 31), eager=True
                ),
                "precipitation": [1.0] * 366,
                "pet": [2.0] * 366,
                "streamflow": [0.5] * 366,
                "temperature": [10.0] * 366,
            }
        )

        with (
            patch(
                "holmes.api.calibration.data.read_data", return_value=mock_data
            ),
            patch(
                "holmes.api.calibration.data.read_cemaneige_info",
                side_effect=HolmesDataError("CemaNeige info not found"),
            ),
        ):
            client = TestClient(create_app())
            with client.websocket_connect("/calibration/") as ws:
                ws.send_json(
                    {
                        "type": "manual",
                        "data": {
                            "catchment": "MockCatchment",
                            "start": "2000-01-01",
                            "end": "2000-12-31",
                            "hydroModel": "gr4j",
                            "snowModel": "cemaneige",
                            "hydroParams": [100.0, 0.0, 50.0, 2.0],
                            "objective": "nse",
                            "transformation": "none",
                        },
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "cemaneige" in response["data"].lower()

    def test_manual_calibration_with_snow_model_missing_temperature(self):
        """Manual calibration with snow model fails when temperature is missing."""
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
            patch(
                "holmes.api.calibration.data.read_data", return_value=mock_data
            ),
            patch(
                "holmes.api.calibration.data.read_cemaneige_info",
                return_value=mock_cemaneige,
            ),
        ):
            client = TestClient(create_app())
            with client.websocket_connect("/calibration/") as ws:
                ws.send_json(
                    {
                        "type": "manual",
                        "data": {
                            "catchment": "MockCatchment",
                            "start": "2000-01-01",
                            "end": "2000-12-31",
                            "hydroModel": "gr4j",
                            "snowModel": "cemaneige",
                            "hydroParams": [100.0, 0.0, 50.0, 2.0],
                            "objective": "nse",
                            "transformation": "none",
                        },
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "temperature" in response["data"].lower()

    def test_calibration_start_with_snow_model_invalid_cemaneige_info(self):
        """Calibration start with snow model fails when cemaneige info is invalid."""
        mock_data = pl.DataFrame(
            {
                "date": pl.date_range(
                    pl.date(2000, 1, 1), pl.date(2000, 6, 30), eager=True
                ),
                "precipitation": [1.0] * 182,
                "pet": [2.0] * 182,
                "streamflow": [0.5] * 182,
                "temperature": [10.0] * 182,
            }
        )

        with (
            patch(
                "holmes.api.calibration.data.read_data", return_value=mock_data
            ),
            patch(
                "holmes.api.calibration.data.read_cemaneige_info",
                side_effect=HolmesDataError("CemaNeige info not found"),
            ),
        ):
            client = TestClient(create_app())
            with client.websocket_connect("/calibration/") as ws:
                ws.send_json(
                    {
                        "type": "calibration_start",
                        "data": {
                            "catchment": "MockCatchment",
                            "start": "2000-01-01",
                            "end": "2000-06-30",
                            "hydroModel": "gr4j",
                            "snowModel": "cemaneige",
                            "objective": "nse",
                            "transformation": "none",
                            "algorithm": "sce",
                            "algorithmParams": {
                                "n_complexes": 2,
                                "k_stop": 3,
                                "p_convergence_threshold": 0.1,
                                "geometric_range_threshold": 0.001,
                                "max_evaluations": 50,
                            },
                        },
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "cemaneige" in response["data"].lower()

    def test_calibration_start_with_snow_model_missing_temperature(self):
        """Calibration start with snow model fails when temperature is missing."""
        mock_data = pl.DataFrame(
            {
                "date": pl.date_range(
                    pl.date(2000, 1, 1), pl.date(2000, 6, 30), eager=True
                ),
                "precipitation": [1.0] * 182,
                "pet": [2.0] * 182,
                "streamflow": [0.5] * 182,
            }
        )

        mock_cemaneige = {
            "qnbv": 1.0,
            "altitude_layers": [500.0, 1000.0],
            "median_altitude": 750.0,
            "latitude": 45.0,
        }

        with (
            patch(
                "holmes.api.calibration.data.read_data", return_value=mock_data
            ),
            patch(
                "holmes.api.calibration.data.read_cemaneige_info",
                return_value=mock_cemaneige,
            ),
        ):
            client = TestClient(create_app())
            with client.websocket_connect("/calibration/") as ws:
                ws.send_json(
                    {
                        "type": "calibration_start",
                        "data": {
                            "catchment": "MockCatchment",
                            "start": "2000-01-01",
                            "end": "2000-06-30",
                            "hydroModel": "gr4j",
                            "snowModel": "cemaneige",
                            "objective": "nse",
                            "transformation": "none",
                            "algorithm": "sce",
                            "algorithmParams": {
                                "n_complexes": 2,
                                "k_stop": 3,
                                "p_convergence_threshold": 0.1,
                                "geometric_range_threshold": 0.001,
                                "max_evaluations": 50,
                            },
                        },
                    }
                )
                response = ws.receive_json()
                assert response["type"] == "error"
                assert "temperature" in response["data"].lower()

    def test_calibration_start_without_snow_model(self):
        """Calibration start works without snow model."""
        client = TestClient(create_app())
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "calibration_start",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2000-06-30",
                        "hydroModel": "gr4j",
                        "snowModel": None,
                        "objective": "nse",
                        "transformation": "none",
                        "algorithm": "sce",
                        "algorithmParams": {
                            "n_complexes": 2,
                            "k_stop": 3,
                            "p_convergence_threshold": 0.1,
                            "geometric_range_threshold": 0.001,
                            "max_evaluations": 50,
                        },
                    },
                }
            )
            # Should receive at least one result message
            response = ws.receive_json()
            assert response["type"] == "result"
            assert "simulation" in response["data"]
