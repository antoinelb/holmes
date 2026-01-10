"""Unit tests for holmes.app module."""

import os
from unittest.mock import patch

from starlette.applications import Starlette

from holmes.app import create_app


class TestCreateApp:
    """Tests for create_app function."""

    def test_create_app_returns_starlette_instance(self):
        """create_app returns a Starlette application."""
        app = create_app()
        assert isinstance(app, Starlette)

    def test_create_app_has_routes(self):
        """create_app includes routes."""
        app = create_app()
        assert len(app.routes) > 0

    @patch("holmes.app.config")
    def test_create_app_debug_mode(self, mock_config):
        """create_app respects debug configuration."""
        mock_config.DEBUG = True
        app = create_app()
        assert app.debug is True

    @patch("holmes.app.config")
    def test_create_app_production_mode(self, mock_config):
        """create_app sets debug=False in production."""
        mock_config.DEBUG = False
        app = create_app()
        assert app.debug is False


class TestRunServer:
    """Tests for run_server function."""

    @patch("holmes.app.uvicorn.run")
    @patch("holmes.app.init_logging")
    @patch("holmes.app.config")
    def test_run_server_calls_uvicorn(
        self, mock_config, mock_init_logging, mock_uvicorn_run
    ):
        """run_server starts uvicorn with correct parameters."""
        mock_config.DEBUG = False
        mock_config.HOST = "127.0.0.1"
        mock_config.PORT = 8000
        mock_config.RELOAD = False

        # Set PYTEST_CURRENT_TEST to prevent browser opening
        os.environ["PYTEST_CURRENT_TEST"] = "test"

        from holmes.app import run_server

        with patch("sys.argv", ["holmes"]):
            run_server()

        mock_uvicorn_run.assert_called_once()
        call_kwargs = mock_uvicorn_run.call_args[1]
        assert call_kwargs["host"] == "127.0.0.1"
        assert call_kwargs["port"] == 8000
        assert call_kwargs["factory"] is True

    @patch("holmes.app.uvicorn.run")
    @patch("holmes.app.init_logging")
    @patch("holmes.app.config")
    def test_run_server_debug_mode(
        self, mock_config, mock_init_logging, mock_uvicorn_run
    ):
        """run_server uses debug log level in debug mode."""
        mock_config.DEBUG = True
        mock_config.HOST = "127.0.0.1"
        mock_config.PORT = 8000
        mock_config.RELOAD = True

        os.environ["PYTEST_CURRENT_TEST"] = "test"

        from holmes.app import run_server

        with patch("sys.argv", ["holmes"]):
            run_server()

        call_kwargs = mock_uvicorn_run.call_args[1]
        assert call_kwargs["log_level"] == "debug"
        assert call_kwargs["reload"] is True

    @patch("holmes.app.uvicorn.run")
    @patch("holmes.app.init_logging")
    @patch("holmes.app.config")
    def test_run_server_production_mode(
        self, mock_config, mock_init_logging, mock_uvicorn_run
    ):
        """run_server uses info log level in production mode."""
        mock_config.DEBUG = False
        mock_config.HOST = "0.0.0.0"
        mock_config.PORT = 80
        mock_config.RELOAD = False

        os.environ["PYTEST_CURRENT_TEST"] = "test"

        from holmes.app import run_server

        with patch("sys.argv", ["holmes"]):
            run_server()

        call_kwargs = mock_uvicorn_run.call_args[1]
        assert call_kwargs["log_level"] == "info"
        assert call_kwargs["reload"] is False
