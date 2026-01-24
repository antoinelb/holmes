"""
Data loading utilities for HOLMES.

This module provides functions for loading catchment observation data,
CemaNeige snow model configuration, and climate projection data.
"""

import csv
import logging
from datetime import timedelta
from functools import lru_cache
from typing import Any

import numpy as np
import polars as pl
from holmes.exceptions import HolmesDataError
from holmes.utils.paths import data_dir
from holmes.validation import validate_catchment_exists, validate_date_range

logger = logging.getLogger("holmes")

# Required columns in observation CSV files (core functionality)
OBSERVATION_REQUIRED_COLUMNS = {"Date", "P", "E0", "Qo"}

# Optional columns (needed for snow modeling)
OBSERVATION_OPTIONAL_COLUMNS = {"T"}

# Required keys in CemaNeige info files
CEMANEIGE_REQUIRED_KEYS = {"AltiBand", "QNBV", "Z50", "Lat"}


##########
# public #
##########


def read_data(
    catchment: str,
    start: str,
    end: str,
    *,
    warmup_length: int = 3,
) -> tuple[pl.DataFrame, int]:
    """
    Read observation data for a catchment within a date range.

    Parameters
    ----------
    catchment : str
        Catchment name
    start : str
        Start date in "%Y-%m-%d" format
    end : str
        End date in "%Y-%m-%d" format
    warmup_length : int
        Number of years for warmup period (default 3)

    Returns
    -------
    pl.DataFrame
        DataFrame with columns: date, precipitation, pet, streamflow, temperature
    int
        Number of warmup steps at the start of the dataframe (to exclude from objectives)

    Raises
    ------
    HolmesDataError
        If catchment doesn't exist, dates are invalid, or no data in range
    """
    try:
        validate_catchment_exists(catchment)
    except ValueError as exc:
        raise HolmesDataError(str(exc)) from exc

    try:
        start_dt, end_dt = validate_date_range(start, end)
    except ValueError as exc:
        raise HolmesDataError(str(exc)) from exc

    warmup_days = 365 * warmup_length
    warmup_start = start_dt - timedelta(days=warmup_days)

    data_ = read_catchment_data(catchment).rename(
        {
            "Date": "date",
            "P": "precipitation",
            "E0": "pet",
            "Qo": "streamflow",
            "T": "temperature",
        },
        strict=False,
    )

    data_ = data_.filter(pl.col("date").is_between(warmup_start, end_dt))
    data_ = data_.collect()

    warmup_steps = data_.filter(pl.col("date") < start_dt).shape[0]

    if len(data_) == 0:
        raise HolmesDataError(
            f"No data found for catchment '{catchment}' in period {start} to {end}. "
            f"Check that the date range falls within the available data period."
        )

    return data_, warmup_steps


@lru_cache(maxsize=1)
def get_available_catchments() -> (
    tuple[tuple[str, bool, tuple[str, str]], ...]
):
    """
    Determines which catchments are available in the data and if snow info is
    available for each.

    Returns a tuple (for hashability with lru_cache) where each element is:
    (<catchment name>, <snow info is available>, (<period min>, <period max>))

    Returns
    -------
    tuple[tuple[str, bool, tuple[str, str]], ...]
        Available catchments with their metadata
    """
    catchments = [
        file.stem.replace("_Observations", "")
        for file in data_dir.glob("*_Observations.csv")
    ]
    return tuple(
        sorted(
            [
                (
                    catchment,
                    (data_dir / f"{catchment}_CemaNeigeInfo.csv").exists(),
                    _get_available_period(catchment),
                )
                for catchment in catchments
            ],
            key=lambda c: c[0],
        )
    )


def read_catchment_data(catchment: str) -> pl.LazyFrame:
    """
    Read raw catchment observation data as a lazy frame.

    Parameters
    ----------
    catchment : str
        Catchment name

    Returns
    -------
    pl.LazyFrame
        Lazy frame with observation data

    Raises
    ------
    HolmesDataError
        If CSV file is malformed or missing required columns
    """
    path = data_dir / f"{catchment}_Observations.csv"

    # Eagerly check file existence since scan_csv is lazy
    if not path.exists():
        raise HolmesDataError(f"Data file not found: {path}")

    try:
        df = pl.scan_csv(path)
    except pl.exceptions.ComputeError as exc:
        raise HolmesDataError(
            f"Failed to parse CSV file '{path}': {exc}"
        ) from exc
    except PermissionError as exc:
        raise HolmesDataError(f"Permission denied reading '{path}'") from exc

    # P4-DATA-02: Validate required columns exist
    try:
        schema = df.collect_schema()
        actual_columns = set(schema.names())
    except pl.exceptions.ComputeError as exc:
        raise HolmesDataError(
            f"Failed to read schema from '{path}': {exc}"
        ) from exc

    missing_required = OBSERVATION_REQUIRED_COLUMNS - actual_columns
    if missing_required:
        raise HolmesDataError(
            f"CSV file '{path}' is missing required columns: {missing_required}. "
            f"Found columns: {actual_columns}"
        )

    # Warn about missing optional columns (e.g., temperature for snow modeling)
    missing_optional = OBSERVATION_OPTIONAL_COLUMNS - actual_columns
    if missing_optional:
        logger.debug(
            f"CSV file '{path}' is missing optional columns: {missing_optional}. "
            f"Snow modeling may not be available for this catchment."
        )

    return df.with_columns(pl.col("Date").str.strptime(pl.Date, "%Y-%m-%d"))


def read_cemaneige_info(catchment: str) -> dict[str, Any]:
    """
    Read CemaNeige configuration parameters for a catchment.

    Parameters
    ----------
    catchment : str
        Catchment name

    Returns
    -------
    dict
        Dictionary with keys: qnbv, altitude_layers, median_altitude, latitude,
        n_altitude_layers

    Raises
    ------
    HolmesDataError
        If file is missing, malformed, or missing required keys
    """
    path = data_dir / f"{catchment}_CemaNeigeInfo.csv"

    # P4-DATA-06: Handle file errors explicitly
    try:
        with open(path, "r") as csv_file:
            reader = csv.reader(csv_file)
            info = dict(reader)
    except FileNotFoundError as exc:
        raise HolmesDataError(
            f"CemaNeige info file not found for catchment '{catchment}': {path}"
        ) from exc
    except PermissionError as exc:
        raise HolmesDataError(
            f"Permission denied reading CemaNeige file: {path}"
        ) from exc
    except csv.Error as exc:
        raise HolmesDataError(
            f"Failed to parse CemaNeige CSV file '{path}': {exc}"
        ) from exc

    # P4-DATA-07: Validate required keys exist
    missing_keys = CEMANEIGE_REQUIRED_KEYS - set(info.keys())
    if missing_keys:
        raise HolmesDataError(
            f"CemaNeige file '{path}' is missing required keys: {missing_keys}. "
            f"Found keys: {set(info.keys())}"
        )

    # P4-DATA-07: Safe parsing of altitude layers
    try:
        altitude_str = info["AltiBand"]
        if not altitude_str or altitude_str.strip() == "":
            raise HolmesDataError(
                f"Empty AltiBand value in CemaNeige file '{path}'"
            )
        altitude_layers = np.array(
            [float(x.strip()) for x in altitude_str.split(";") if x.strip()]
        )
        if len(altitude_layers) == 0:
            raise HolmesDataError(
                f"No altitude layers found in AltiBand: '{altitude_str}'"
            )
    except ValueError as exc:
        raise HolmesDataError(
            f"Invalid altitude layer value in '{path}': {exc}"
        ) from exc

    # Safe parsing of numeric values
    try:
        qnbv = float(info["QNBV"])
        median_altitude = float(info["Z50"])
        latitude = float(info["Lat"])
    except ValueError as exc:
        raise HolmesDataError(
            f"Invalid numeric value in CemaNeige file '{path}': {exc}"
        ) from exc

    return {
        "qnbv": qnbv,
        "altitude_layers": altitude_layers,
        "median_altitude": median_altitude,
        "latitude": latitude,
        "n_altitude_layers": len(altitude_layers),
    }


def read_projection_data(catchment: str) -> pl.LazyFrame:
    """
    Read climate projection data for a catchment.

    Parameters
    ----------
    catchment : str
        Catchment name

    Returns
    -------
    pl.LazyFrame
        Lazy frame with projection data

    Raises
    ------
    HolmesDataError
        If file not found or malformed
    """
    path = data_dir / f"{catchment}_Projections.csv"

    # Eagerly check file existence since scan_csv is lazy
    if not path.exists():
        raise HolmesDataError(f"Projection data file not found: {path}")

    try:
        return pl.scan_csv(path).with_columns(
            pl.col("date").str.strptime(pl.Date, "%Y-%m-%d")
        )
    except PermissionError as exc:
        raise HolmesDataError(
            f"Permission denied reading projection file: {path}"
        ) from exc
    except pl.exceptions.ComputeError as exc:
        raise HolmesDataError(
            f"Failed to parse projection CSV file '{path}': {exc}"
        ) from exc


###########
# private #
###########


def _get_available_period(catchment: str) -> tuple[str, str]:
    """
    Gets the minimum and maximum available dates for the given catchment.

    Parameters
    ----------
    catchment : str
        Catchment name

    Returns
    -------
    tuple[str, str]
        Tuple of (minimum date, maximum date) as strings

    Raises
    ------
    HolmesDataError
        If the catchment doesn't correspond to an available data file
    """
    path = data_dir / f"{catchment}_Observations.csv"

    # Eagerly check file existence since scan_csv is lazy
    if not path.exists():
        raise HolmesDataError(f"Data file not found: '{path}'")

    try:
        min_max = (
            pl.scan_csv(path)
            .select(
                pl.col("Date").min().alias("min"),
                pl.col("Date").max().alias("max"),
            )
            .collect()
        )
    except pl.exceptions.ComputeError as exc:
        raise HolmesDataError(
            f"Failed to read date range from '{path}': {exc}"
        ) from exc

    return min_max[0, 0], min_max[0, 1]
