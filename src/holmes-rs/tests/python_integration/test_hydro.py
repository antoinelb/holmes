"""
Tests for hydro module PyO3 bindings.

These tests verify that GR4J and Bucket models work correctly from Python.
"""

import numpy as np
import pytest
from numpy.testing import assert_almost_equal

from holmes_rs import HolmesValidationError
from holmes_rs.hydro import bucket, gr4j


class TestGr4jInit:
    """Tests for gr4j.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = gr4j.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 4 elements."""
        defaults, _ = gr4j.init()

        assert len(defaults) == 4

    def test_bounds_shape(self):
        """Bounds should be 4x2 array."""
        _, bounds = gr4j.init()

        assert bounds.shape == (4, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = gr4j.init()

        for i in range(4):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = gr4j.init()

        for i in range(4):
            assert bounds[i, 0] < bounds[i, 1]


class TestGr4jSimulate:
    """Tests for gr4j.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = gr4j.init()

        streamflow = gr4j.simulate(defaults, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = gr4j.init()

        streamflow = gr4j.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = gr4j.init()

        streamflow = gr4j.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = gr4j.init()
        precip = np.zeros(100)

        streamflow = gr4j.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([100.0, 0.5, 50.0])  # Only 3 params

        with pytest.raises(HolmesValidationError, match="param"):
            gr4j.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = gr4j.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            gr4j.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([300.0, 0.5, 100.0, 2.5])

        streamflow = gr4j.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestGr4jParamNames:
    """Tests for gr4j.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(gr4j, "param_names")

    def test_param_names_count(self):
        """Should have 4 parameter names."""
        assert len(gr4j.param_names) == 4

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        assert gr4j.param_names == ["x1", "x2", "x3", "x4"]


class TestBucketInit:
    """Tests for bucket.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = bucket.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 6 elements."""
        defaults, _ = bucket.init()

        assert len(defaults) == 6

    def test_bounds_shape(self):
        """Bounds should be 6x2 array."""
        _, bounds = bucket.init()

        assert bounds.shape == (6, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = bucket.init()

        for i in range(6):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]


class TestBucketSimulate:
    """Tests for bucket.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = bucket.init()

        streamflow = bucket.simulate(defaults, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = bucket.init()

        streamflow = bucket.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = bucket.init()

        streamflow = bucket.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([100.0, 0.5, 50.0, 3.0])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            bucket.simulate(wrong_params, sample_precipitation, sample_pet)


class TestBucketParamNames:
    """Tests for bucket.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(bucket, "param_names")

    def test_param_names_count(self):
        """Should have 6 parameter names."""
        assert len(bucket.param_names) == 6

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["c_soil", "alpha", "k_r", "delta", "beta", "k_t"]
        assert bucket.param_names == expected


class TestHydroModuleIntegration:
    """Integration tests for hydro module."""

    def test_module_structure(self):
        """Hydro module should have correct submodules."""
        from holmes_rs import hydro

        assert hasattr(hydro, "gr4j")
        assert hasattr(hydro, "bucket")

    def test_both_models_produce_output(self, sample_precipitation, sample_pet):
        """Both models should produce valid streamflow."""
        gr4j_defaults, _ = gr4j.init()
        bucket_defaults, _ = bucket.init()

        gr4j_flow = gr4j.simulate(
            gr4j_defaults, sample_precipitation, sample_pet
        )
        bucket_flow = bucket.simulate(
            bucket_defaults, sample_precipitation, sample_pet
        )

        assert len(gr4j_flow) == len(sample_precipitation)
        assert len(bucket_flow) == len(sample_precipitation)
        assert np.all(np.isfinite(gr4j_flow))
        assert np.all(np.isfinite(bucket_flow))
