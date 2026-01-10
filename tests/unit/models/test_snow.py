"""Unit tests for holmes.models.snow module."""

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from holmes import data
from holmes.models import snow


class TestGetModel:
    """Tests for get_model function."""

    def test_get_model_cemaneige(self):
        """Returns CemaNeige simulate function."""
        simulate = snow.get_model("cemaneige")
        assert callable(simulate)

    def test_cemaneige_simulate(self):
        """CemaNeige simulate produces output."""
        simulate = snow.get_model("cemaneige")
        cemaneige_info = data.read_cemaneige_info("Au Saumon")
        n = 365
        params = np.array([0.25, 3.74, cemaneige_info["qnbv"]])
        precipitation = np.random.uniform(0, 20, n)
        temperature = np.random.uniform(-20, 30, n)
        day_of_year = np.array([i % 365 + 1 for i in range(n)], dtype=np.uintp)
        elevation_layers = cemaneige_info["altitude_layers"]
        median_elevation = cemaneige_info["median_altitude"]
        result = simulate(
            params,
            precipitation,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)

    def test_cemaneige_transforms_precipitation(self):
        """CemaNeige transforms precipitation differently in cold/warm."""
        simulate = snow.get_model("cemaneige")
        cemaneige_info = data.read_cemaneige_info("Au Saumon")
        n = 365
        params = np.array([0.25, 3.74, cemaneige_info["qnbv"]])
        precipitation = np.ones(n) * 10.0
        temperature_cold = np.ones(n) * -10.0
        temperature_warm = np.ones(n) * 20.0
        day_of_year = np.array([i % 365 + 1 for i in range(n)], dtype=np.uintp)
        elevation_layers = cemaneige_info["altitude_layers"]
        median_elevation = cemaneige_info["median_altitude"]
        result_cold = simulate(
            params,
            precipitation,
            temperature_cold,
            day_of_year,
            elevation_layers,
            median_elevation,
        )
        result_warm = simulate(
            params,
            precipitation,
            temperature_warm,
            day_of_year,
            elevation_layers,
            median_elevation,
        )
        # Warm temps should have precipitation pass through more directly
        assert not np.allclose(result_cold, result_warm)


class TestHypothesis:
    """Property-based tests for snow model."""

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=10)
    def test_cemaneige_output_length_matches_input(self, precipitation):
        """CemaNeige output length matches input length."""
        simulate = snow.get_model("cemaneige")
        cemaneige_info = data.read_cemaneige_info("Au Saumon")
        n = len(precipitation)
        params = np.array([0.25, 3.74, cemaneige_info["qnbv"]])
        precip = np.array(precipitation)
        temperature = np.random.uniform(-20, 30, n)
        day_of_year = np.array([i % 365 + 1 for i in range(n)], dtype=np.uintp)
        elevation_layers = cemaneige_info["altitude_layers"]
        median_elevation = cemaneige_info["median_altitude"]
        result = simulate(
            params,
            precip,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )
        assert len(result) == n

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=10)
    def test_cemaneige_output_non_negative(self, precipitation):
        """CemaNeige output is non-negative."""
        simulate = snow.get_model("cemaneige")
        cemaneige_info = data.read_cemaneige_info("Au Saumon")
        n = len(precipitation)
        params = np.array([0.25, 3.74, cemaneige_info["qnbv"]])
        precip = np.array(precipitation)
        temperature = np.random.uniform(-20, 30, n)
        day_of_year = np.array([i % 365 + 1 for i in range(n)], dtype=np.uintp)
        elevation_layers = cemaneige_info["altitude_layers"]
        median_elevation = cemaneige_info["median_altitude"]
        result = simulate(
            params,
            precip,
            temperature,
            day_of_year,
            elevation_layers,
            median_elevation,
        )
        assert np.all(result >= 0)
