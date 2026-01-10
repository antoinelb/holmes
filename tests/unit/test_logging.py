"""Unit tests for holmes.logging module."""

import logging
from unittest.mock import patch


from holmes.logging import RouteFilter, init_logging


class TestInitLogging:
    """Tests for init_logging function."""

    def test_init_logging_configures_holmes_logger(self):
        """init_logging creates holmes logger."""
        init_logging()
        logger = logging.getLogger("holmes")
        assert logger is not None
        assert len(logger.handlers) > 0

    @patch("holmes.logging.config")
    def test_init_logging_debug_level(self, mock_config):
        """init_logging sets DEBUG level in debug mode."""
        mock_config.DEBUG = True
        init_logging()
        logger = logging.getLogger("holmes")
        assert logger.level == logging.DEBUG

    @patch("holmes.logging.config")
    def test_init_logging_info_level(self, mock_config):
        """init_logging sets INFO level in production mode."""
        mock_config.DEBUG = False
        init_logging()
        logger = logging.getLogger("holmes")
        assert logger.level == logging.INFO


class TestRouteFilter:
    """Tests for RouteFilter class."""

    def test_route_filter_init(self):
        """RouteFilter can be initialized."""
        filter_instance = RouteFilter()
        assert filter_instance is not None

    def test_route_filter_allows_non_route_messages(self):
        """RouteFilter allows non-route log messages."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Some other message",
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is True

    def test_route_filter_blocks_ping_route(self):
        """RouteFilter blocks /ping GET 200 requests."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"GET /ping HTTP/1.1" 200',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is False

    def test_route_filter_blocks_index_route(self):
        """RouteFilter blocks / GET 200 requests."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"GET / HTTP/1.1" 200',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is False

    def test_route_filter_blocks_static_js_route(self):
        """RouteFilter blocks static JS file requests."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"GET /static/scripts/app.js HTTP/1.1" 200',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is False

    def test_route_filter_blocks_static_css_route(self):
        """RouteFilter blocks static CSS file requests."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"GET /static/styles/main.css HTTP/1.1" 200',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is False

    def test_route_filter_allows_error_responses(self):
        """RouteFilter allows non-200 responses."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"GET /ping HTTP/1.1" 500',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is True

    def test_route_filter_allows_post_requests(self):
        """RouteFilter allows POST requests to filtered routes."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"POST /ping HTTP/1.1" 200',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is True

    def test_route_filter_allows_api_routes(self):
        """RouteFilter allows API route requests."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"GET /calibration/ HTTP/1.1" 200',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is True

    def test_route_filter_blocks_ping_with_query_string(self):
        """RouteFilter blocks /ping with query parameters."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"GET /ping?foo=bar HTTP/1.1" 200',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is False

    def test_route_filter_blocks_index_with_query_string(self):
        """RouteFilter blocks / with query parameters."""
        filter_instance = RouteFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg='"GET /?test=1 HTTP/1.1" 200',
            args=(),
            exc_info=None,
        )
        assert filter_instance.filter(record) is False
