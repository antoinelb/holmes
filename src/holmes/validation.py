"""
Input validation utilities for HOLMES.

This module provides pure validation functions for validating user input,
configuration values, and data before processing.
"""

import ipaddress
import re
from datetime import datetime
from typing import Sequence

import numpy as np
import numpy.typing as npt

from holmes.utils.paths import data_dir

__all__ = [
    "validate_date_format",
    "validate_date_range",
    "validate_catchment_exists",
    "validate_port",
    "validate_host",
    "validate_array_no_nan",
    "validate_array_length",
    "validate_parameter_bounds",
    "validate_ws_message_keys",
]


def validate_date_format(
    date_str: str, format_str: str = "%Y-%m-%d"
) -> datetime:
    """
    Parse and validate a date string.

    Parameters
    ----------
    date_str : str
        Date string to validate
    format_str : str
        Expected date format, defaults to "%Y-%m-%d"

    Returns
    -------
    datetime
        Parsed datetime object

    Raises
    ------
    ValueError
        If the date string doesn't match the expected format
    """
    try:
        return datetime.strptime(date_str, format_str)
    except ValueError as exc:
        raise ValueError(
            f"Invalid date format '{date_str}'. Expected format: {format_str}"
        ) from exc


def validate_date_range(start: str, end: str) -> tuple[datetime, datetime]:
    """
    Validate that start date is before end date.

    Parameters
    ----------
    start : str
        Start date string in "%Y-%m-%d" format
    end : str
        End date string in "%Y-%m-%d" format

    Returns
    -------
    tuple[datetime, datetime]
        Tuple of (start_datetime, end_datetime)

    Raises
    ------
    ValueError
        If dates are invalid format or start >= end
    """
    start_dt = validate_date_format(start)
    end_dt = validate_date_format(end)

    if start_dt >= end_dt:
        raise ValueError(
            f"Start date ({start}) must be before end date ({end})"
        )

    return start_dt, end_dt


def validate_catchment_exists(catchment: str) -> None:
    """
    Validate that a catchment data file exists.

    Parameters
    ----------
    catchment : str
        Catchment name to validate

    Raises
    ------
    ValueError
        If the catchment data file doesn't exist
    """
    path = data_dir / f"{catchment}_Observations.csv"
    if not path.exists():
        available = sorted(
            f.stem.replace("_Observations", "")
            for f in data_dir.glob("*_Observations.csv")
        )
        raise ValueError(
            f"Catchment '{catchment}' not found. "
            f"Available catchments: {', '.join(available)}"
        )


def validate_port(port: int) -> int:
    """
    Validate that a port number is in the valid range.

    Parameters
    ----------
    port : int
        Port number to validate

    Returns
    -------
    int
        The validated port number

    Raises
    ------
    ValueError
        If port is not in range 1-65535
    """
    if not 1 <= port <= 65535:
        raise ValueError(f"Port {port} is invalid. Must be in range 1-65535")
    return port


def validate_host(host: str) -> str:
    """
    Validate that a host is a valid IP address or hostname.

    Parameters
    ----------
    host : str
        Host string to validate (IP address or hostname)

    Returns
    -------
    str
        The validated host string

    Raises
    ------
    ValueError
        If host is not a valid IP address or hostname
    """
    # Try as IP address first
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass

    # Check if it looks like an IP address (all numeric parts separated by dots)
    # If so, reject it since it failed IP validation above
    ip_like_pattern = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
    if ip_like_pattern.match(host):
        raise ValueError(
            f"Invalid host '{host}'. Must be a valid IP address or hostname"
        )

    # Validate as hostname
    # RFC 1123 hostname pattern
    hostname_pattern = re.compile(
        r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)$"
        r"|^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63}(?<!-))*$"
    )
    if hostname_pattern.match(host):
        return host

    raise ValueError(
        f"Invalid host '{host}'. Must be a valid IP address or hostname"
    )


def validate_array_no_nan(arr: npt.NDArray[np.floating], name: str) -> None:
    """
    Validate that an array contains no NaN or infinity values.

    Parameters
    ----------
    arr : np.ndarray
        Array to validate
    name : str
        Name of the array for error messages

    Raises
    ------
    ValueError
        If the array contains NaN or infinity values
    """
    if not np.isfinite(arr).all():
        nan_indices = np.where(~np.isfinite(arr))[0]
        raise ValueError(
            f"Array '{name}' contains NaN or infinity values at indices: "
            f"{nan_indices[:5].tolist()}{'...' if len(nan_indices) > 5 else ''}"
        )


def validate_array_length(arr: npt.NDArray, expected: int, name: str) -> None:
    """
    Validate that an array has the expected length.

    Parameters
    ----------
    arr : np.ndarray
        Array to validate
    expected : int
        Expected length
    name : str
        Name of the array for error messages

    Raises
    ------
    ValueError
        If the array length doesn't match expected
    """
    if len(arr) != expected:
        raise ValueError(
            f"Array '{name}' has length {len(arr)}, expected {expected}"
        )


def validate_parameter_bounds(
    params: npt.NDArray[np.floating],
    bounds: Sequence[tuple[float, float]],
    names: Sequence[str],
) -> None:
    """
    Validate that parameters fall within their defined bounds.

    Parameters
    ----------
    params : np.ndarray
        Parameter values to validate
    bounds : Sequence[tuple[float, float]]
        List of (lower, upper) bounds for each parameter
    names : Sequence[str]
        Names of parameters for error messages

    Raises
    ------
    ValueError
        If any parameter is outside its bounds
    """
    for value, (lower, upper), name in zip(params, bounds, names, strict=True):
        if not lower <= value <= upper:
            raise ValueError(
                f"Parameter '{name}' value {value} is outside bounds "
                f"[{lower}, {upper}]"
            )


def validate_ws_message_keys(
    msg: dict, required_keys: Sequence[str], context: str = "message"
) -> None:
    """
    Validate that a WebSocket message contains all required keys.

    Parameters
    ----------
    msg : dict
        Message dictionary to validate
    required_keys : Sequence[str]
        List of required keys
    context : str
        Context string for error messages

    Raises
    ------
    ValueError
        If any required keys are missing
    """
    missing = [key for key in required_keys if key not in msg]
    if missing:
        raise ValueError(
            f"Missing required keys in {context}: {', '.join(missing)}"
        )
