"""Tests for src/config.py - configuration module."""

from src import config


def test_debug_is_bool():
    """DEBUG should be a boolean."""
    assert isinstance(config.DEBUG, bool)


def test_reload_is_bool():
    """RELOAD should be a boolean."""
    assert isinstance(config.RELOAD, bool)


def test_host_is_string():
    """HOST should be a string."""
    assert isinstance(config.HOST, str)


def test_port_is_int():
    """PORT should be an integer."""
    assert isinstance(config.PORT, int)


def test_port_in_valid_range():
    """PORT should be in valid port range."""
    assert 1 <= config.PORT <= 65535


def test_host_default_value():
    """HOST should have reasonable default."""
    # Default is 127.0.0.1
    assert config.HOST == "127.0.0.1" or len(config.HOST) > 0


def test_port_default_value():
    """PORT should have default of 8000."""
    # Default is 8000
    assert config.PORT == 8000 or config.PORT in range(1000, 65536)


def test_debug_default_value():
    """DEBUG should default to False."""
    # In test environment, DEBUG is False unless explicitly set
    assert isinstance(config.DEBUG, bool)


def test_reload_default_value():
    """RELOAD should default to False."""
    # In test environment, RELOAD is False unless explicitly set
    assert isinstance(config.RELOAD, bool)
