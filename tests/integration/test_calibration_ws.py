"""Integration tests for calibration WebSocket handler."""

import pytest
from starlette.testclient import TestClient

from holmes.app import create_app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(create_app())


class TestCalibrationWebSocket:
    """Tests for calibration WebSocket handler."""

    def test_config_message(self, client):
        """Config request returns expected structure."""
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json({"type": "config"})
            response = ws.receive_json()
            assert response["type"] == "config"
            data = response["data"]
            assert "hydro_model" in data
            assert "catchment" in data
            assert "snow_model" in data
            assert "objective" in data
            assert "transformation" in data
            assert "algorithm" in data

    def test_observations_message(self, client):
        """Load observations returns data."""
        with client.websocket_connect("/calibration/") as ws:
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

    def test_observations_missing_params(self, client):
        """Error for missing params."""
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "observations",
                    "data": {
                        "catchment": "Au Saumon"
                    },  # Missing start and end
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"

    def test_manual_calibration(self, client):
        """Manual calibration flow returns result."""
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "manual",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2001-12-31",
                        "hydroModel": "gr4j",
                        "snowModel": None,
                        "hydroParams": [350, 0.5, 90, 1.7],
                        "objective": "nse",
                        "transformation": "none",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "result"
            data = response["data"]
            assert "done" in data
            assert "simulation" in data
            assert "params" in data
            assert "objective" in data

    def test_manual_calibration_missing_params(self, client):
        """Error handling for missing params."""
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "manual",
                    "data": {
                        "catchment": "Au Saumon",
                        # Missing other required params
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"

    def test_calibration_start_completes(self, client):
        """Automatic calibration completes with small max_evaluations."""
        with client.websocket_connect("/calibration/") as ws:
            # Start calibration with very low max_evaluations to finish quickly
            ws.send_json(
                {
                    "type": "calibration_start",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2001-12-31",
                        "hydroModel": "gr4j",
                        "snowModel": None,
                        "objective": "nse",
                        "transformation": "none",
                        "algorithm": "sce",
                        "algorithmParams": {
                            "n_complexes": 2,
                            "k_stop": 2,
                            "p_convergence_threshold": 0.1,
                            "geometric_range_threshold": 0.001,
                            "max_evaluations": 20,
                        },
                    },
                }
            )
            # Receive results until done
            results = []
            for _ in range(50):  # Safety limit
                response = ws.receive_json()
                assert response["type"] == "result"
                results.append(response["data"])
                if response["data"]["done"]:
                    break
            # Should have received at least one result
            assert len(results) >= 1
            # Last result should be done
            assert results[-1]["done"] is True

    def test_unknown_message_type(self, client):
        """Error for unknown type."""
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json({"type": "unknown_type"})
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "Unknown" in response["data"]

    def test_manual_calibration_snow_model_missing_cemaneige_info(
        self, client
    ):
        """Error when snow model requested but catchment has no CemaNeige info."""
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "manual",
                    "data": {
                        "catchment": "Leaf",  # Has no CemaNeige info file
                        "start": "1980-01-01",
                        "end": "1981-12-31",
                        "hydroModel": "gr4j",
                        "snowModel": "cemaneige",
                        "hydroParams": [350, 0.5, 90, 1.7],
                        "objective": "nse",
                        "transformation": "none",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "CemaNeige" in response["data"]

    def test_calibration_start_snow_model_missing_cemaneige_info(self, client):
        """Error when snow model requested but catchment has no CemaNeige info."""
        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "calibration_start",
                    "data": {
                        "catchment": "Leaf",  # Has no CemaNeige info file
                        "start": "1980-01-01",
                        "end": "1981-12-31",
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
                            "max_evaluations": 20,
                        },
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "CemaNeige" in response["data"]


class TestCalibrationWebSocketSnowModelMissingTemperature:
    """Tests for snow model with catchments missing temperature data."""

    def test_manual_calibration_snow_model_missing_temperature(
        self, client, monkeypatch
    ):
        """Error when snow model requested but catchment has no temperature."""
        from holmes import data as data_module

        original_read_data = data_module.read_data

        def mock_read_data(catchment, start, end, **kwargs):
            """Return data without temperature column."""
            df = original_read_data(catchment, start, end, **kwargs)
            # Remove temperature column to simulate catchment without temp data
            return df.drop("temperature")

        monkeypatch.setattr(data_module, "read_data", mock_read_data)

        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "manual",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2001-12-31",
                        "hydroModel": "gr4j",
                        "snowModel": "cemaneige",
                        "hydroParams": [350, 0.5, 90, 1.7],
                        "objective": "nse",
                        "transformation": "none",
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "temperature" in response["data"].lower()

    def test_calibration_start_snow_model_missing_temperature(
        self, client, monkeypatch
    ):
        """Error when snow model requested but catchment has no temperature."""
        from holmes import data as data_module

        original_read_data = data_module.read_data

        def mock_read_data(catchment, start, end, **kwargs):
            """Return data without temperature column."""
            df = original_read_data(catchment, start, end, **kwargs)
            # Remove temperature column to simulate catchment without temp data
            return df.drop("temperature")

        monkeypatch.setattr(data_module, "read_data", mock_read_data)

        with client.websocket_connect("/calibration/") as ws:
            ws.send_json(
                {
                    "type": "calibration_start",
                    "data": {
                        "catchment": "Au Saumon",
                        "start": "2000-01-01",
                        "end": "2001-12-31",
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
                            "max_evaluations": 20,
                        },
                    },
                }
            )
            response = ws.receive_json()
            assert response["type"] == "error"
            assert "temperature" in response["data"].lower()
