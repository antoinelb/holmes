"""Shared fixtures for Holmes tests."""

import numpy as np
import numpy.typing as npt
import polars as pl
import pytest
from starlette.testclient import TestClient

from holmes import data
from holmes.app import create_app
from holmes.models import hydro

# Available catchments
CATCHMENTS = ["Au Saumon", "Baskatong", "Leaf"]
SNOW_CATCHMENTS = ["Au Saumon", "Baskatong"]
HYDRO_MODELS = ["gr4j", "bucket"]


@pytest.fixture
def app():
    """Create a test application instance."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client for the application."""
    return TestClient(app)


@pytest.fixture(params=CATCHMENTS)
def catchment(request):
    """Parametrized fixture for all catchments."""
    return request.param


@pytest.fixture(params=SNOW_CATCHMENTS)
def snow_catchment(request):
    """Parametrized fixture for catchments with snow data."""
    return request.param


@pytest.fixture(params=HYDRO_MODELS)
def hydro_model(request):
    """Parametrized fixture for hydro models."""
    return request.param


@pytest.fixture
def au_saumon_data() -> pl.DataFrame:
    """Load Au Saumon catchment data for testing."""
    return data.read_data("Au Saumon", "2000-01-01", "2005-12-31")


@pytest.fixture
def baskatong_data() -> pl.DataFrame:
    """Load Baskatong catchment data for testing."""
    return data.read_data("Baskatong", "2000-01-01", "2005-12-31")


@pytest.fixture
def leaf_data() -> pl.DataFrame:
    """Load Leaf catchment data for testing."""
    return data.read_data("Leaf", "2000-01-01", "2005-12-31")


@pytest.fixture
def au_saumon_cemaneige() -> dict:
    """Load Au Saumon CemaNeige info."""
    return data.read_cemaneige_info("Au Saumon")


@pytest.fixture
def baskatong_cemaneige() -> dict:
    """Load Baskatong CemaNeige info."""
    return data.read_cemaneige_info("Baskatong")


def calculate_mean_baseline_nse(
    observations: npt.NDArray[np.float64],
) -> float:
    """Calculate NSE for predicting catchment mean.

    NSE = 1 - sum((obs - sim)^2) / sum((obs - obs_mean)^2)
    For mean prediction, sim = obs_mean, so NSE = 0.
    """
    return 0.0


def calculate_median_baseline_nse(
    observations: npt.NDArray[np.float64],
) -> float:
    """Calculate NSE for predicting catchment median."""
    obs_mean = np.mean(observations)
    obs_median = np.median(observations)
    numerator = np.sum((observations - obs_median) ** 2)
    denominator = np.sum((observations - obs_mean) ** 2)
    return 1.0 - numerator / denominator


def calculate_doy_mean_baseline_nse(
    observations: npt.NDArray[np.float64],
    day_of_year: npt.NDArray[np.uintp],
) -> float:
    """Calculate NSE for predicting day-of-year mean."""
    obs_mean = np.mean(observations)
    doy_means = np.zeros_like(observations)
    for doy in range(1, 367):
        mask = day_of_year == doy
        if np.any(mask):
            doy_means[mask] = np.mean(observations[mask])
    numerator = np.sum((observations - doy_means) ** 2)
    denominator = np.sum((observations - obs_mean) ** 2)
    return 1.0 - numerator / denominator


def calculate_doy_median_baseline_nse(
    observations: npt.NDArray[np.float64],
    day_of_year: npt.NDArray[np.uintp],
) -> float:
    """Calculate NSE for predicting day-of-year median."""
    obs_mean = np.mean(observations)
    doy_medians = np.zeros_like(observations)
    for doy in range(1, 367):
        mask = day_of_year == doy
        if np.any(mask):
            doy_medians[mask] = np.median(observations[mask])
    numerator = np.sum((observations - doy_medians) ** 2)
    denominator = np.sum((observations - obs_mean) ** 2)
    return 1.0 - numerator / denominator


def get_model_defaults(model: str) -> npt.NDArray[np.float64]:
    """Get default parameters for a hydro model."""
    config = hydro.get_config(model)
    return np.array([p["default"] for p in config])
