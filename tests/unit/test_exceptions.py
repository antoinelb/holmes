"""Tests for HOLMES exception hierarchy."""

import pytest

from holmes.exceptions import (
    HolmesConfigError,
    HolmesDataError,
    HolmesError,
    HolmesNumericalError,
    HolmesValidationError,
    HolmesWebSocketError,
)


class TestRustExceptions:
    """Tests for re-exported Rust exceptions."""

    def test_holmes_error_is_importable(self):
        """HolmesError should be importable from exceptions module."""
        assert HolmesError is not None

    def test_holmes_numerical_error_is_subclass(self):
        """HolmesNumericalError should be a subclass of HolmesError."""
        # Note: This tests the inheritance defined in Rust
        assert issubclass(HolmesNumericalError, HolmesError)

    def test_holmes_validation_error_is_subclass(self):
        """HolmesValidationError should be a subclass of HolmesError."""
        assert issubclass(HolmesValidationError, HolmesError)


class TestPythonExceptions:
    """Tests for Python-specific exceptions."""

    def test_data_error_message(self):
        """HolmesDataError should preserve error message."""
        error = HolmesDataError("Test data error")
        assert str(error) == "Test data error"

    def test_data_error_is_exception(self):
        """HolmesDataError should be an Exception subclass."""
        assert issubclass(HolmesDataError, Exception)

    def test_websocket_error_message(self):
        """HolmesWebSocketError should preserve error message."""
        error = HolmesWebSocketError("Connection failed")
        assert str(error) == "Connection failed"

    def test_websocket_error_is_exception(self):
        """HolmesWebSocketError should be an Exception subclass."""
        assert issubclass(HolmesWebSocketError, Exception)

    def test_config_error_message(self):
        """HolmesConfigError should preserve error message."""
        error = HolmesConfigError("Invalid port")
        assert str(error) == "Invalid port"

    def test_config_error_is_exception(self):
        """HolmesConfigError should be an Exception subclass."""
        assert issubclass(HolmesConfigError, Exception)


class TestExceptionChaining:
    """Tests for exception chaining with 'from exc' pattern."""

    def test_data_error_chain(self):
        """HolmesDataError should support exception chaining."""
        original = ValueError("original error")
        chained = HolmesDataError("wrapped error")
        chained.__cause__ = original

        assert chained.__cause__ is original
        assert str(chained.__cause__) == "original error"

    def test_websocket_error_chain(self):
        """HolmesWebSocketError should support exception chaining."""
        original = OSError("connection reset")
        chained = HolmesWebSocketError("send failed")
        chained.__cause__ = original

        assert chained.__cause__ is original

    def test_config_error_chain(self):
        """HolmesConfigError should support exception chaining."""
        original = ValueError("bad value")
        chained = HolmesConfigError("config invalid")
        chained.__cause__ = original

        assert chained.__cause__ is original


class TestExceptionRaising:
    """Tests for raising and catching exceptions."""

    def test_raise_data_error(self):
        """HolmesDataError should be raisable and catchable."""
        with pytest.raises(HolmesDataError) as exc_info:
            raise HolmesDataError("test message")
        assert "test message" in str(exc_info.value)

    def test_raise_websocket_error(self):
        """HolmesWebSocketError should be raisable and catchable."""
        with pytest.raises(HolmesWebSocketError) as exc_info:
            raise HolmesWebSocketError("test message")
        assert "test message" in str(exc_info.value)

    def test_raise_config_error(self):
        """HolmesConfigError should be raisable and catchable."""
        with pytest.raises(HolmesConfigError) as exc_info:
            raise HolmesConfigError("test message")
        assert "test message" in str(exc_info.value)

    def test_catch_as_exception(self):
        """All custom exceptions should be catchable as Exception."""
        for exc_class in [
            HolmesDataError,
            HolmesWebSocketError,
            HolmesConfigError,
        ]:
            with pytest.raises(Exception):
                raise exc_class("test")
