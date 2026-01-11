"""
Tests for snow module PyO3 bindings.

These tests verify that CemaNeige snow model works correctly from Python.
"""

import numpy as np
import pytest

from holmes_rs import HolmesValidationError
from holmes_rs.snow import cemaneige


class TestCemaNeigeInit:
    """Tests for cemaneige.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = cemaneige.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 3 elements."""
        defaults, _ = cemaneige.init()

        assert len(defaults) == 3

    def test_bounds_shape(self):
        """Bounds should be 3x2 array."""
        _, bounds = cemaneige.init()

        assert bounds.shape == (3, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = cemaneige.init()

        for i in range(3):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = cemaneige.init()

        for i in range(3):
            assert bounds[i, 0] < bounds[i, 1]


class TestCemaNeigeSimulate:
    """Tests for cemaneige.simulate function."""

    def test_output_length(
        self,
        sample_precipitation,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
    ):
        """Output should have same length as input."""
        defaults, _ = cemaneige.init()
        median_elevation = 1000.0

        effective_precip = cemaneige.simulate(
            defaults,
            sample_precipitation,
            sample_temperature,
            sample_doy,
            sample_elevation_layers,
            median_elevation,
        )

        assert len(effective_precip) == len(sample_precipitation)

    def test_nonnegative_output(
        self,
        sample_precipitation,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
    ):
        """All effective precipitation values should be non-negative."""
        defaults, _ = cemaneige.init()
        median_elevation = 1000.0

        effective_precip = cemaneige.simulate(
            defaults,
            sample_precipitation,
            sample_temperature,
            sample_doy,
            sample_elevation_layers,
            median_elevation,
        )

        assert np.all(effective_precip >= 0)

    def test_finite_output(
        self,
        sample_precipitation,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
    ):
        """All output values should be finite."""
        defaults, _ = cemaneige.init()
        median_elevation = 1000.0

        effective_precip = cemaneige.simulate(
            defaults,
            sample_precipitation,
            sample_temperature,
            sample_doy,
            sample_elevation_layers,
            median_elevation,
        )

        assert np.all(np.isfinite(effective_precip))

    def test_warm_conditions_no_snow(self):
        """Warm conditions should pass precipitation through as liquid."""
        defaults, _ = cemaneige.init()
        n = 30

        precip = np.full(n, 5.0)
        temp = np.full(n, 15.0)  # Warm - no snow
        doy = np.arange(1, n + 1, dtype=np.uint64)
        elevation_layers = np.array([1000.0])
        median_elevation = 1000.0

        effective_precip = cemaneige.simulate(
            defaults, precip, temp, doy, elevation_layers, median_elevation
        )

        # Warm temps should result in effective precip close to input
        assert np.sum(effective_precip) > 0.5 * np.sum(precip)

    def test_cold_conditions_snow_accumulation(self):
        """Cold conditions should accumulate snow."""
        defaults, _ = cemaneige.init()
        n = 30

        precip = np.full(n, 5.0)
        temp = np.full(n, -10.0)  # Very cold - all snow
        doy = np.arange(1, n + 1, dtype=np.uint64)
        elevation_layers = np.array([1000.0])
        median_elevation = 1000.0

        effective_precip = cemaneige.simulate(
            defaults, precip, temp, doy, elevation_layers, median_elevation
        )

        # Cold temps should result in reduced effective precip (snow accumulates)
        assert np.sum(effective_precip) < np.sum(precip)

    def test_multiple_elevation_layers(
        self, sample_precipitation, sample_temperature, sample_doy
    ):
        """Should work with multiple elevation layers."""
        defaults, _ = cemaneige.init()
        elevation_layers = np.array([500.0, 1000.0, 1500.0, 2000.0, 2500.0])
        median_elevation = 1500.0

        effective_precip = cemaneige.simulate(
            defaults,
            sample_precipitation,
            sample_temperature,
            sample_doy,
            elevation_layers,
            median_elevation,
        )

        assert len(effective_precip) == len(sample_precipitation)
        assert np.all(np.isfinite(effective_precip))

    def test_single_elevation_layer(
        self, sample_precipitation, sample_temperature, sample_doy
    ):
        """Should work with single elevation layer."""
        defaults, _ = cemaneige.init()
        elevation_layers = np.array([1000.0])
        median_elevation = 1000.0

        effective_precip = cemaneige.simulate(
            defaults,
            sample_precipitation,
            sample_temperature,
            sample_doy,
            elevation_layers,
            median_elevation,
        )

        assert len(effective_precip) == len(sample_precipitation)

    def test_param_count_error(
        self,
        sample_precipitation,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
    ):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([0.5, 5.0])  # Only 2 params

        with pytest.raises(HolmesValidationError, match="param"):
            cemaneige.simulate(
                wrong_params,
                sample_precipitation,
                sample_temperature,
                sample_doy,
                sample_elevation_layers,
                1000.0,
            )

    def test_length_mismatch_error(
        self, sample_precipitation, sample_doy, sample_elevation_layers
    ):
        """Should raise error for mismatched input lengths."""
        defaults, _ = cemaneige.init()
        short_temp = np.array([0.0, 0.0])

        with pytest.raises(HolmesValidationError, match="length"):
            cemaneige.simulate(
                defaults,
                sample_precipitation,
                short_temp,
                sample_doy,
                sample_elevation_layers,
                1000.0,
            )

    def test_custom_params(
        self,
        sample_precipitation,
        sample_temperature,
        sample_doy,
        sample_elevation_layers,
    ):
        """Should work with custom parameter values."""
        params = np.array([0.5, 5.0, 350.0])
        median_elevation = 1000.0

        effective_precip = cemaneige.simulate(
            params,
            sample_precipitation,
            sample_temperature,
            sample_doy,
            sample_elevation_layers,
            median_elevation,
        )

        assert len(effective_precip) == len(sample_precipitation)
        assert np.all(np.isfinite(effective_precip))


class TestCemaNeigeParamNames:
    """Tests for cemaneige.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(cemaneige, "param_names")

    def test_param_names_count(self):
        """Should have 3 parameter names."""
        assert len(cemaneige.param_names) == 3

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        assert cemaneige.param_names == ["ctg", "kf", "qnbv"]


class TestSnowModuleIntegration:
    """Integration tests for snow module."""

    def test_module_structure(self):
        """Snow module should have correct submodules."""
        from holmes_rs import snow

        assert hasattr(snow, "cemaneige")

    def test_cemaneige_functions(self):
        """CemaNeige module should have required functions."""
        assert hasattr(cemaneige, "init")
        assert hasattr(cemaneige, "simulate")
        assert callable(cemaneige.init)
        assert callable(cemaneige.simulate)
