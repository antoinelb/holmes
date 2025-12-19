"""Tests for __main__.py module."""

from unittest.mock import patch


def test_main_module_calls_run_server():
    """Test that the __main__ module calls run_server."""
    with patch("holmes.app.run_server") as mock_run_server:
        # Import the module to trigger the call
        import holmes.__main__  # noqa: F401

        # Verify run_server was called
        mock_run_server.assert_called_once()
