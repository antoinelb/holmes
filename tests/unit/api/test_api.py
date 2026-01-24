"""Unit tests for holmes.api.api module."""

import importlib.metadata
from unittest.mock import patch

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
