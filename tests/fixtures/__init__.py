"""Test fixtures for HOLMES v3 tests."""

import numpy as np
import polars as pl
import pytest
from pathlib import Path


@pytest.fixture
def fixtures_dir():
    """Path to fixtures directory."""
    return Path(__file__).parent


@pytest.fixture
def sample_catchment_data():
    """Generate sample catchment observation data."""
    n_days = 365
    dates = pl.date_range(
        start=pl.date(2020, 1, 1),
        end=pl.date(2020, 12, 31),
        interval="1d",
        eager=True
    )

    return pl.DataFrame({
        "Date": dates,
        "P": np.random.uniform(0, 20, n_days),
        "E0": np.random.uniform(0, 5, n_days),
        "Qo": np.random.uniform(0, 15, n_days),
        "T": np.random.uniform(-5, 25, n_days),
    })


@pytest.fixture
def sample_gr4j_params():
    """Default GR4J parameters."""
    return {
        "x1": 350,
        "x2": 0.0,
        "x3": 50,
        "x4": 2.0,
    }


@pytest.fixture
def sample_calibration_result():
    """Sample calibration result structure."""
    return {
        "params": {
            "x1": [300, 320, 350],
            "x2": [-0.5, -0.2, 0.0],
            "x3": [45, 48, 50],
            "x4": [1.8, 2.0, 2.2],
        },
        "objective": [0.75, 0.80, 0.85],
    }


@pytest.fixture
def mock_plotly_figure():
    """Mock Plotly figure for testing."""
    import plotly.graph_objects as go
    return go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[1, 2, 3])])


@pytest.fixture
def sample_hydro_data():
    """Sample hydrological data for testing."""
    n = 100
    return pl.DataFrame({
        "precipitation": np.random.uniform(0, 20, n),
        "evapotranspiration": np.random.uniform(0, 5, n),
        "flow": np.random.uniform(0, 15, n),
    })


@pytest.fixture
def perfect_match():
    """Perfect simulation matching observations."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    return obs, sim


@pytest.fixture
def poor_match():
    """Poor simulation."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    return obs, sim


@pytest.fixture
def sample_precipitation_evap():
    """Sample precipitation and evapotranspiration data."""
    n_days = 365
    precip = np.random.uniform(0, 20, n_days)
    evap = np.random.uniform(0, 5, n_days)
    return precip, evap
