"""
Custom exceptions for HOLMES.

This module provides a unified exception hierarchy for the HOLMES application,
re-exporting Rust exceptions and adding Python-specific exceptions.
"""

# Re-export Rust exceptions for unified exception handling
# These are raised by the holmes_rs extension for numerical and validation errors
from holmes_rs import (
    HolmesError,
    HolmesNumericalError,
    HolmesValidationError,
)

__all__ = [
    # Rust exceptions
    "HolmesError",
    "HolmesNumericalError",
    "HolmesValidationError",
    # Python exceptions
    "HolmesDataError",
    "HolmesWebSocketError",
    "HolmesConfigError",
]


class HolmesDataError(Exception):
    """
    Raised for data loading and parsing errors.

    This exception is used when:
    - CSV files are malformed or have missing columns
    - Required data files are not found
    - Date ranges are invalid or yield empty results
    - CemaNeige configuration parsing fails
    """


class HolmesWebSocketError(Exception):
    """
    Raised for WebSocket communication errors.

    This exception is used when:
    - WebSocket send operations fail
    - Connection state is invalid
    - Message parsing fails
    """


class HolmesConfigError(Exception):
    """
    Raised for configuration validation errors.

    This exception is used when:
    - Environment variables have invalid values
    - Port numbers are out of range
    - Host addresses are invalid
    """
