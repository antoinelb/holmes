"""Tests for app module."""

import pytest
from unittest.mock import MagicMock, patch
from starlette.applications import Starlette
from src.app import create_app, run_server


class TestCreateApp:
    """Tests for create_app function."""

    @patch("src.app.init_logging")
    @patch("src.app.logger")
    def test_create_app_returns_starlette(self, mock_logger, mock_init_logging):
        """Test that create_app returns a Starlette app."""
        app = create_app()

        assert isinstance(app, Starlette)
        mock_init_logging.assert_called_once()
        mock_logger.info.assert_called_once_with("App started.")

    @patch("src.app.init_logging")
    @patch("src.app.logger")
    @patch("src.app.config")
    def test_create_app_debug_mode(self, mock_config, mock_logger, mock_init_logging):
        """Test create_app in debug mode."""
        mock_config.DEBUG = True

        app = create_app()

        assert app.debug is True
        assert mock_logger.warning.called
        assert mock_logger.warning.call_args[0][0] == "Running in debug mode."

    @patch("src.app.init_logging")
    @patch("src.app.logger")
    @patch("src.app.config")
    def test_create_app_production_mode(
        self, mock_config, mock_logger, mock_init_logging
    ):
        """Test create_app in production mode."""
        mock_config.DEBUG = False

        app = create_app()

        assert app.debug is False


class TestRunServer:
    """Tests for run_server function."""

    @patch("src.app.uvicorn.run")
    @patch("src.app.init_logging")
    @patch("src.app.logger")
    @patch("src.app.config")
    def test_run_server_debug_mode(
        self, mock_config, mock_logger, mock_init_logging, mock_uvicorn_run
    ):
        """Test run_server in debug mode."""
        mock_config.DEBUG = True
        mock_config.HOST = "localhost"
        mock_config.PORT = 8000
        mock_config.RELOAD = True

        run_server()

        mock_init_logging.assert_called_once()
        assert mock_logger.info.called
        assert "debug" in mock_logger.info.call_args[0][0]
        mock_uvicorn_run.assert_called_once()

        # Check uvicorn.run call arguments
        call_kwargs = mock_uvicorn_run.call_args.kwargs
        assert call_kwargs["host"] == "localhost"
        assert call_kwargs["port"] == 8000
        assert call_kwargs["reload"] is True
        assert call_kwargs["log_level"] == "debug"
        assert call_kwargs["access_log"] is True

    @patch("src.app.uvicorn.run")
    @patch("src.app.init_logging")
    @patch("src.app.logger")
    @patch("src.app.config")
    def test_run_server_production_mode(
        self, mock_config, mock_logger, mock_init_logging, mock_uvicorn_run
    ):
        """Test run_server in production mode."""
        mock_config.DEBUG = False
        mock_config.HOST = "0.0.0.0"
        mock_config.PORT = 8080
        mock_config.RELOAD = False

        run_server()

        mock_init_logging.assert_called_once()
        assert mock_logger.info.called
        assert "production" in mock_logger.info.call_args[0][0]
        mock_uvicorn_run.assert_called_once()

        # Check uvicorn.run call arguments
        call_kwargs = mock_uvicorn_run.call_args.kwargs
        assert call_kwargs["host"] == "0.0.0.0"
        assert call_kwargs["port"] == 8080
        assert call_kwargs["reload"] is False
        assert call_kwargs["log_level"] == "info"
        assert call_kwargs["access_log"] is True
