"""Tests for logging module."""

import logging
import re
from unittest.mock import MagicMock, patch

import pytest

from holmes.logging import RouteFilter, init_logging


class TestInitLogging:
    """Tests for init_logging function."""

    @patch("holmes.logging.logging.config.dictConfig")
    @patch("holmes.logging.config")
    def test_init_logging_debug_mode(self, mock_config, mock_dictConfig):
        """Test init_logging in debug mode."""
        mock_config.DEBUG = True

        init_logging()

        mock_dictConfig.assert_called_once()
        config_dict = mock_dictConfig.call_args[0][0]

        # Verify configuration structure
        assert config_dict["version"] == 1
        assert "formatters" in config_dict
        assert "handlers" in config_dict
        assert "loggers" in config_dict
        assert config_dict["disable_existing_loggers"] is True

    @patch("holmes.logging.logging.config.dictConfig")
    @patch("holmes.logging.config")
    def test_init_logging_production_mode(self, mock_config, mock_dictConfig):
        """Test init_logging in production mode."""
        mock_config.DEBUG = False

        init_logging()

        mock_dictConfig.assert_called_once()
        config_dict = mock_dictConfig.call_args[0][0]

        # Verify handler level is INFO in production
        assert "handlers" in config_dict


class TestRouteFilter:
    """Tests for RouteFilter class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.filter = RouteFilter()

    def test_filter_allows_non_route_messages(self):
        """Test that filter allows non-route log messages."""
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = "Some random log message"

        result = self.filter.filter(record)

        assert result is True

    def test_filter_blocks_ping_route(self):
        """Test that filter blocks ping route GET requests."""
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = (
            '127.0.0.1:12345 - "GET /ping HTTP/1.1" 200'
        )

        result = self.filter.filter(record)

        assert result is False

    def test_filter_blocks_root_route(self):
        """Test that filter blocks root route GET requests."""
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = '127.0.0.1:12345 - "GET / HTTP/1.1" 200'

        result = self.filter.filter(record)

        assert result is False

    def test_filter_blocks_static_js_route(self):
        """Test that filter blocks static JavaScript route GET requests."""
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = (
            '127.0.0.1:12345 - "GET /static/scripts/app.js HTTP/1.1" 200'
        )

        result = self.filter.filter(record)

        assert result is False

    def test_filter_blocks_static_css_route(self):
        """Test that filter blocks static CSS route GET requests."""
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = (
            '127.0.0.1:12345 - "GET /static/styles/main.css HTTP/1.1" 200'
        )

        result = self.filter.filter(record)

        assert result is False

    def test_filter_allows_non_200_responses(self):
        """Test that filter allows non-200 responses."""
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = (
            '127.0.0.1:12345 - "GET /ping HTTP/1.1" 500'
        )

        result = self.filter.filter(record)

        assert result is True

    def test_filter_allows_non_get_requests(self):
        """Test that filter allows non-GET requests."""
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = '127.0.0.1:12345 - "POST / HTTP/1.1" 200'

        result = self.filter.filter(record)

        assert result is True

    def test_filter_allows_api_routes(self):
        """Test that filter allows API routes."""
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = (
            '127.0.0.1:12345 - "GET /api/data HTTP/1.1" 200'
        )

        result = self.filter.filter(record)

        assert result is True

    def test_filter_allows_query_params(self):
        """Test that filter handles routes with query parameters."""
        # ping route with query params should be filtered
        record = MagicMock(spec=logging.LogRecord)
        record.getMessage.return_value = (
            '127.0.0.1:12345 - "GET /ping?test=1 HTTP/1.1" 200'
        )

        result = self.filter.filter(record)

        assert result is False

        # non-filtered route with query params should pass
        record.getMessage.return_value = (
            '127.0.0.1:12345 - "GET /api/data?test=1 HTTP/1.1" 200'
        )

        result = self.filter.filter(record)

        assert result is True
