"""Tests for src/api/api.py - main API routes."""

import pytest
from starlette.testclient import TestClient

from holmes.app import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


class TestPingRoute:
    """Tests for /ping endpoint."""

    def test_ping_returns_pong(self, client):
        """Ping endpoint should return 'Pong!'."""
        response = client.get("/ping")
        assert response.status_code == 200
        assert response.text == "Pong!"


class TestVersionRoute:
    """Tests for /version endpoint."""

    def test_version_returns_version_string(self, client):
        """Version endpoint should return version from pyproject.toml."""
        response = client.get("/version")
        assert response.status_code == 200
        # Version should be a valid version string
        version = response.text
        assert len(version) > 0
        # Should match semver pattern roughly
        assert "." in version

    @pytest.mark.asyncio
    async def test_version_missing_from_pyproject(self):
        """Test error handling when version is missing from pyproject.toml."""
        from unittest.mock import patch

        from starlette.requests import Request

        from holmes.api import api

        # Mock importlib.metadata.version to raise an exception
        with patch(
            "holmes.api.api.importlib.metadata.version",
            side_effect=Exception("No version"),
        ):

            async def dummy_receive():
                return {"type": "http.request"}

            request = Request({"type": "http", "method": "GET"}, dummy_receive)
            response = await api._get_version(request)

            assert response.status_code == 500
            assert isinstance(response.body, bytes)
            assert "Unknown version" in response.body.decode()


class TestIndexRoute:
    """Tests for / (index) endpoint."""

    def test_index_returns_html(self, client):
        """Index should return HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        # Should contain some HTML
        assert "<html" in response.text or "<!DOCTYPE" in response.text


class TestPrecompileRoute:
    """Tests for /precompile endpoint."""

    def test_precompile_returns_success(self, client):
        """Precompile endpoint should return 200."""
        response = client.get("/precompile")
        assert response.status_code == 200


class TestStaticFiles:
    """Tests for /static/* routes."""

    def test_static_files_accessible(self, client):
        """Static files should be accessible."""
        # Try to access the index.html via static (if it exists there)
        # This will depend on what static files actually exist
        response = client.get("/static/index.html")
        # Should either exist (200) or not found (404), but not error (500)
        assert response.status_code in [200, 404]
