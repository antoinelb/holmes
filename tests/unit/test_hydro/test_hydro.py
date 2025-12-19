"""Tests for holmes.hydro.hydro - main hydro interface."""

from datetime import date

import numpy as np
import polars as pl
import pytest
from holmes.hydro import hydro
from holmes import data


# Test precompile


@pytest.mark.asyncio
async def test_precompile_executes_without_error():
    """Precompile should execute without raising."""
    await hydro.precompile()


# Test run_model


def test_run_model_gr4j(sample_hydro_data):
    """Should run GR4J model."""
    params = {"x1": 350, "x2": 0.0, "x3": 50, "x4": 2.0}
    result = hydro.run_model(sample_hydro_data, "GR4J", params)
    assert isinstance(result, np.ndarray)
    assert len(result) == len(sample_hydro_data)


def test_run_model_case_insensitive(sample_hydro_data):
    """Model name should be case-insensitive."""
    params = {"x1": 350, "x2": 0.0, "x3": 50, "x4": 2.0}
    result1 = hydro.run_model(sample_hydro_data, "GR4J", params)
    result2 = hydro.run_model(sample_hydro_data, "gr4j", params)
    np.testing.assert_array_equal(result1, result2)


def test_run_model_lowercase(sample_hydro_data):
    """Should work with lowercase model name."""
    params = {"x1": 350, "x2": 0.0, "x3": 50, "x4": 2.0}
    result = hydro.run_model(sample_hydro_data, "gr4j", params)
    assert isinstance(result, np.ndarray)


def test_run_model_uppercase(sample_hydro_data):
    """Should work with uppercase model name."""
    params = {"x1": 350, "x2": 0.0, "x3": 50, "x4": 2.0}
    result = hydro.run_model(sample_hydro_data, "GR4J", params)
    assert isinstance(result, np.ndarray)


def test_run_model_invalid_model_raises_error(sample_hydro_data):
    """Invalid model should raise ValueError."""
    with pytest.raises(ValueError, match="only available hydrological models"):
        hydro.run_model(sample_hydro_data, "InvalidModel", {})


def test_run_model_with_integer_params(sample_hydro_data):
    """Should handle integer parameters correctly."""
    params = {"x1": 350, "x2": 0.0, "x3": 50, "x4": 2.0}
    result = hydro.run_model(sample_hydro_data, "GR4J", params)
    assert np.all(result >= 0)


def test_run_model_extracts_correct_columns(sample_hydro_data):
    """Should extract precipitation and evapotranspiration from dataframe."""
    params = {"x1": 350, "x2": 0.0, "x3": 50, "x4": 2.0}
    result = hydro.run_model(sample_hydro_data, "GR4J", params)
    assert len(result) == len(sample_hydro_data)


# Test read_transformed_hydro_data


@pytest.mark.requires_data
def test_read_transformed_hydro_data_returns_dataframe():
    """Should return DataFrame with required columns."""
    catchments = data.get_available_catchments()
    if not catchments:
        pytest.skip("No catchment data available")

    catchment = catchments[0][0]
    _, _, (start, end) = catchments[0]

    result = hydro.read_transformed_hydro_data(catchment, start, end, "none")

    assert isinstance(result, pl.DataFrame)
    assert "date" in result.columns
    assert "precipitation" in result.columns
    assert "evapotranspiration" in result.columns
    assert "flow" in result.columns


@pytest.mark.requires_data
def test_read_transformed_hydro_data_warmup_period_included():
    """Should include warmup period in returned data."""
    from datetime import datetime

    catchments = data.get_available_catchments()
    if not catchments:
        pytest.skip("No catchment data available")

    catchment, _, (min_date, max_date) = catchments[0]
    # Use dates that are guaranteed to be in the middle of the available period
    # to avoid edge effects
    start_year = int(min_date[:4]) + 2  # Start 2 years after min
    start = f"{start_year}-06-01"
    end = f"{start_year}-08-31"

    result = hydro.read_transformed_hydro_data(
        catchment, start, end, "none", warmup_length=1
    )

    # Should have approximately 92 days + 365 days warmup
    assert len(result) > 365
    # First date should be before start date
    first_date = result["date"].min()
    assert isinstance(first_date, date)
    assert first_date < datetime.strptime(start, "%Y-%m-%d").date()


@pytest.mark.requires_data
def test_read_transformed_hydro_data_custom_warmup():
    """Should respect custom warmup length."""
    catchments = data.get_available_catchments()
    if not catchments:
        pytest.skip("No catchment data available")

    catchment, _, (min_date, max_date) = catchments[0]
    # Use dates well within the available range
    start_year = int(min_date[:4]) + 3
    start = f"{start_year}-01-01"
    end = f"{start_year}-12-31"

    result_short = hydro.read_transformed_hydro_data(
        catchment, start, end, "none", warmup_length=1
    )
    result_long = hydro.read_transformed_hydro_data(
        catchment, start, end, "none", warmup_length=2
    )

    # Longer warmup should have more data (approximately 365 more days)
    assert len(result_long) > len(result_short)
    assert len(result_long) - len(result_short) > 300  # Approximately 1 year


@pytest.mark.requires_data
def test_read_transformed_hydro_data_renames_columns():
    """Should rename columns correctly."""
    catchments = data.get_available_catchments()
    if not catchments:
        pytest.skip("No catchment data available")

    catchment = catchments[0][0]
    _, _, (start, end) = catchments[0]

    result = hydro.read_transformed_hydro_data(catchment, start, end, "none")

    # Check for renamed columns
    assert "date" in result.columns
    assert "precipitation" in result.columns
    assert "evapotranspiration" in result.columns
    assert "flow" in result.columns
    assert "temperature" in result.columns

    # Original column names should not exist
    assert "Date" not in result.columns
    assert "P" not in result.columns
    assert "E0" not in result.columns
    assert "Qo" not in result.columns
    assert "T" not in result.columns


@pytest.mark.requires_data
def test_read_transformed_hydro_data_filters_date_range():
    """Should filter data to specified date range (plus warmup)."""

    catchments = data.get_available_catchments()
    if not catchments:
        pytest.skip("No catchment data available")

    catchment, _, (min_date, max_date) = catchments[0]
    # Use dates well within the available range
    start_year = int(min_date[:4]) + 2
    start = f"{start_year}-06-01"
    end = f"{start_year}-08-31"

    result = hydro.read_transformed_hydro_data(
        catchment, start, end, "none", warmup_length=0
    )

    # Should have approximately 92 days (June + July + August)
    # Allowing some flexibility for exact date calculations
    assert 85 < len(result) < 100


@pytest.mark.requires_data
def test_read_transformed_hydro_data_with_snow_model_none():
    """Should work with 'none' snow model."""
    catchments = data.get_available_catchments()
    if not catchments:
        pytest.skip("No catchment data available")

    catchment = catchments[0][0]
    _, _, (start, end) = catchments[0]

    result = hydro.read_transformed_hydro_data(catchment, start, end, "none")

    assert isinstance(result, pl.DataFrame)
    assert len(result) > 0


@pytest.mark.requires_data
def test_read_transformed_hydro_data_default_warmup():
    """Should use default warmup of 3 years."""

    catchments = data.get_available_catchments()
    if not catchments:
        pytest.skip("No catchment data available")

    catchment, _, (min_date, max_date) = catchments[0]
    # Use dates well within the available range (need at least 3 years of history)
    start_year = (
        int(min_date[:4]) + 4
    )  # Start 4 years after min to ensure warmup available
    start = f"{start_year}-01-01"
    end = f"{start_year}-12-31"

    result = hydro.read_transformed_hydro_data(catchment, start, end, "none")

    # Default warmup is 3 years = 1095 days
    # Plus the year itself = approximately 1460 days
    expected_min_days = 1095 + 300  # Some margin
    assert len(result) >= expected_min_days


@pytest.mark.requires_data
def test_read_transformed_hydro_data_returns_collected_dataframe():
    """Should return collected (not lazy) DataFrame."""
    catchments = data.get_available_catchments()
    if not catchments:
        pytest.skip("No catchment data available")

    catchment = catchments[0][0]
    _, _, (start, end) = catchments[0]

    result = hydro.read_transformed_hydro_data(catchment, start, end, "none")

    # Should be DataFrame, not LazyFrame
    assert isinstance(result, pl.DataFrame)
    assert not isinstance(result, pl.LazyFrame)
