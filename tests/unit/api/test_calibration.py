"""Unit tests for holmes.api.calibration module."""

import pytest
from starlette.testclient import TestClient

from holmes.app import create_app


class TestCalibrationWebSocket:
    """Tests for calibration WebSocket handler."""

    def test_get_routes(self):
        """get_routes returns WebSocket routes."""
        from holmes.api.calibration import get_routes

        routes = get_routes()
        assert len(routes) == 1
        assert routes[0].path == "/"

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
            ws.send_json({
                "type": "observations",
                "data": {
                    "catchment": "Au Saumon",
                    "start": "2000-01-01",
                    "end": "2000-12-31",
                },
            })
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
            ws.send_json({
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
            })
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
            ws.send_json({
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
            })
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
            ws.send_json({
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
            })
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
            ws.send_json({
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
            })
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
