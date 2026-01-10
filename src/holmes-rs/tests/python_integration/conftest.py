"""
Pytest configuration and shared fixtures for Python integration tests.

These tests verify the PyO3 bindings work correctly from Python.
"""

import pytest
import numpy as np


@pytest.fixture
def sample_precipitation():
    """Generate sample precipitation data."""
    np.random.seed(42)
    return np.maximum(0, np.random.normal(5.0, 3.0, 100))


@pytest.fixture
def sample_pet():
    """Generate sample PET data."""
    np.random.seed(43)
    return np.maximum(0, np.random.normal(3.0, 1.0, 100))


@pytest.fixture
def sample_temperature():
    """Generate sample temperature data with seasonal variation."""
    np.random.seed(44)
    t = np.arange(100)
    seasonal = 10 * np.sin(2 * np.pi * t / 365)
    return 10 + seasonal + np.random.normal(0, 2, 100)


@pytest.fixture
def sample_doy():
    """Generate sample day of year data."""
    return np.arange(1, 101, dtype=np.uint64)


@pytest.fixture
def sample_elevation_layers():
    """Generate sample elevation layers."""
    return np.array([500.0, 1000.0, 1500.0])


@pytest.fixture
def sample_observations(sample_precipitation, sample_pet):
    """Generate synthetic observations using GR4J with default params."""
    from holmes_rs.hydro import gr4j

    defaults, _ = gr4j.init()
    return gr4j.simulate(defaults, sample_precipitation, sample_pet) * 1.1
