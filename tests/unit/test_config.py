"""Unit tests for holmes.config module."""

import importlib
import sys
from unittest.mock import patch

import pytest

from holmes.exceptions import HolmesConfigError


class TestConfigValidation:
    """Tests for config validation error handling."""

    def test_invalid_port_raises_config_error(self):
        """Invalid PORT should raise HolmesConfigError on module load."""
        # Remove the module from cache so it can be reimported
        if "holmes.config" in sys.modules:
            del sys.modules["holmes.config"]

        # Mock validate_port to raise ValueError
        with patch(
            "holmes.validation.validate_port",
            side_effect=ValueError("Port must be between 1-65535"),
        ):
            with pytest.raises(HolmesConfigError) as exc_info:
                importlib.import_module("holmes.config")

            assert "Port must be between 1-65535" in str(exc_info.value)

        # Cleanup: reimport with normal validation
        if "holmes.config" in sys.modules:
            del sys.modules["holmes.config"]
        importlib.import_module("holmes.config")

    def test_invalid_host_raises_config_error(self):
        """Invalid HOST should raise HolmesConfigError on module load."""
        # Remove the module from cache so it can be reimported
        if "holmes.config" in sys.modules:
            del sys.modules["holmes.config"]

        # Mock validate_host to raise ValueError (but validate_port should work)
        with patch("holmes.validation.validate_port", return_value=8000):
            with patch(
                "holmes.validation.validate_host",
                side_effect=ValueError("Invalid host format"),
            ):
                with pytest.raises(HolmesConfigError) as exc_info:
                    importlib.import_module("holmes.config")

                assert "Invalid host format" in str(exc_info.value)

        # Cleanup: reimport with normal validation
        if "holmes.config" in sys.modules:
            del sys.modules["holmes.config"]
        importlib.import_module("holmes.config")

    def test_config_loads_with_valid_defaults(self):
        """Config should load successfully with valid defaults."""
        from holmes import config

        assert hasattr(config, "DEBUG")
        assert hasattr(config, "RELOAD")
        assert hasattr(config, "PORT")
        assert hasattr(config, "HOST")
        assert isinstance(config.PORT, int)
        assert isinstance(config.HOST, str)
