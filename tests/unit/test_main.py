"""Tests for __main__.py module."""

import pytest
from unittest.mock import patch


def test_main_module_calls_run_server():
    """Test that the __main__ module calls run_server."""
    with patch("src.app.run_server") as mock_run_server:
        # Import the module to trigger the call
        import src.__main__  # noqa: F401

        # Verify run_server was called
        mock_run_server.assert_called_once()
