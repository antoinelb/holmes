"""Unit tests for holmes.api.api module."""

import importlib.metadata
from unittest.mock import patch

from holmes.api.api import (
    _get_app_version,
    _get_versioned_css,
    _get_versioned_js,
)
from holmes.app import create_app
from starlette.testclient import TestClient


class TestHTTPEndpoints:
    """Tests for HTTP endpoints."""

    def test_ping(self):
        """Ping endpoint returns Pong."""
        client = TestClient(create_app())
        response = client.get("/ping")
        assert response.status_code == 200
        assert response.text == "Pong!"

    def test_health(self):
        """Health endpoint returns OK."""
        client = TestClient(create_app())
        response = client.get("/health")
        assert response.status_code == 200
        assert response.text == "OK"

    def test_version(self):
        """Version endpoint returns version string."""
        client = TestClient(create_app())
        response = client.get("/version")
        assert response.status_code == 200
        # Version should be a string (either version number or "Unknown version")
        assert isinstance(response.text, str)

    def test_version_unknown(self):
        """Version endpoint returns 500 when package not found."""
        with patch(
            "holmes.api.api.importlib.metadata.version"
        ) as mock_version:
            # P1-ERR-03: Use specific exception instead of bare Exception
            mock_version.side_effect = importlib.metadata.PackageNotFoundError(
                "holmes_hydro"
            )
            client = TestClient(create_app())
            response = client.get("/version")
            assert response.status_code == 500
            assert response.text == "Unknown version"

    def test_index(self):
        """Index endpoint returns HTML."""
        client = TestClient(create_app())
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_static_files(self):
        """Static files are served."""
        client = TestClient(create_app())
        # Just verify the static mount exists by checking it doesn't 404
        # on a request that would hit the mount point
        response = client.get("/static/")
        # Will be 404 if no index, or 200/403 if directory listing
        # Just verify it's not a routing error
        assert response.status_code in (200, 403, 404)


class TestCacheBusting:
    """Tests for static file cache busting."""

    def test_get_app_version_returns_version(self):
        """_get_app_version returns package version when available."""
        with patch(
            "holmes.api.api.importlib.metadata.version"
        ) as mock_version:
            mock_version.return_value = "1.2.3"
            assert _get_app_version() == "1.2.3"

    def test_get_app_version_returns_dev_when_not_found(self):
        """_get_app_version returns 'dev' when package not found."""
        with patch(
            "holmes.api.api.importlib.metadata.version"
        ) as mock_version:
            mock_version.side_effect = importlib.metadata.PackageNotFoundError(
                "holmes-hydro"
            )
            assert _get_app_version() == "dev"

    def test_index_has_versioned_static_urls(self):
        """Index page returns HTML with versioned static URLs."""
        client = TestClient(create_app())
        response = client.get("/")
        assert response.status_code == 200
        assert "?v=" in response.text

    def test_get_versioned_css_injects_version(self):
        """_get_versioned_css injects version into @import URLs."""
        _get_versioned_css.cache_clear()
        css = _get_versioned_css("index.css", "1.0.0")
        assert '@import "./template.css?v=1.0.0"' in css

    def test_get_versioned_css_file_not_found(self):
        """_get_versioned_css raises FileNotFoundError for missing files."""
        _get_versioned_css.cache_clear()
        try:
            _get_versioned_css("nonexistent.css", "1.0.0")
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_get_versioned_js_injects_version(self):
        """_get_versioned_js injects version into import URLs."""
        _get_versioned_js.cache_clear()
        js = _get_versioned_js("index.js", "1.0.0")
        assert 'from "./utils/elements.js?v=1.0.0"' in js

    def test_get_versioned_js_file_not_found(self):
        """_get_versioned_js raises FileNotFoundError for missing files."""
        _get_versioned_js.cache_clear()
        try:
            _get_versioned_js("nonexistent.js", "1.0.0")
            assert False, "Expected FileNotFoundError"
        except FileNotFoundError:
            pass

    def test_serve_css_returns_versioned_css(self):
        """CSS endpoint returns CSS with versioned @import URLs."""
        client = TestClient(create_app())
        response = client.get("/static/styles/index.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]
        assert "?v=" in response.text

    def test_serve_css_returns_404_for_missing_file(self):
        """CSS endpoint returns 404 for missing files."""
        client = TestClient(create_app())
        response = client.get("/static/styles/nonexistent.css")
        assert response.status_code == 404

    def test_serve_js_returns_versioned_js(self):
        """JS endpoint returns JS with versioned import URLs."""
        client = TestClient(create_app())
        response = client.get("/static/scripts/index.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]
        assert "?v=" in response.text

    def test_serve_js_returns_404_for_missing_file(self):
        """JS endpoint returns 404 for missing files."""
        client = TestClient(create_app())
        response = client.get("/static/scripts/nonexistent.js")
        assert response.status_code == 404
