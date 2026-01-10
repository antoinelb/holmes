"""Unit tests for holmes.api.projection module."""

import pytest
from starlette.testclient import TestClient

from holmes.app import create_app


class TestProjectionWebSocket:
    """Tests for projection WebSocket handler."""

    def test_get_routes(self):
        """get_routes returns WebSocket routes."""
        from holmes.api.projection import get_routes

        routes = get_routes()
        assert len(routes) == 1
        assert routes[0].path == "/"

    def test_websocket_config_message(self):
        """Config message returns available projections."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            response = ws.receive_json()
            assert response["type"] == "config"
            assert isinstance(response["data"], list)

    def test_websocket_config_missing_data(self):
        """Config message without data sends error."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "catchment must be provided" in response["data"]

    def test_websocket_projection_message(self):
        """Projection message returns climate projection results."""
        # First get available config
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            config_response = ws.receive_json()

            if len(config_response["data"]) > 0:
                # Use first available config
                first_config = config_response["data"][0]
                ws.send_json({
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
                            "hydroParams": {"x1": 100.0, "x2": 0.0, "x3": 50.0, "x4": 2.0},
                        },
                    },
                })
                response = ws.receive_json()
                assert response["type"] == "projection"
                assert isinstance(response["data"], list)

    def test_websocket_projection_without_snow(self):
        """Projection works without snow model."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "config", "data": "Au Saumon"})
            config_response = ws.receive_json()

            if len(config_response["data"]) > 0:
                first_config = config_response["data"][0]
                ws.send_json({
                    "type": "projection",
                    "data": {
                        "config": {
                            "model": first_config["model"],
                            "horizon": first_config["horizon"],
                            "scenario": first_config["scenario"],
                        },
                        "calibration": {
                            "catchment": "Au Saumon",
                            "hydroModel": "bucket",
                            "snowModel": None,
                            "hydroParams": {"c_soil": 100.0, "alpha": 0.5, "k_r": 100.0, "delta": 6.0, "beta": 0.5, "k_t": 200.0},
                        },
                    },
                })
                response = ws.receive_json()
                assert response["type"] == "projection"

    def test_websocket_projection_missing_params(self):
        """Projection without required params returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "projection", "data": {}})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "must be provided" in response["data"]

    def test_websocket_unknown_message_type(self):
        """Unknown message type returns error."""
        client = TestClient(create_app())
        with client.websocket_connect("/projection/") as ws:
            ws.send_json({"type": "unknown_type"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Unknown message type" in response["data"]
