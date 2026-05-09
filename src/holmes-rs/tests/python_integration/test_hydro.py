"""
Tests for hydro module PyO3 bindings.

These tests verify that GR4J and Bucket models work correctly from Python.
"""

import numpy as np
import pytest

from holmes_rs import HolmesValidationError
from holmes_rs.hydro import (
    bucket,
    cequeau,
    crec,
    gardenia,
    gr4j,
    hbv,
    hymod,
    ihacres,
    martine,
    mohyse,
    mordor,
    nam,
    pdm,
    sacramento,
    simhyd,
    smar,
    tank,
    topmodel,
    wageningen,
    xinanjiang,
)


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


class TestGr4jParamDescriptions:
    """Tests for gr4j.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(gr4j, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(gr4j.param_descriptions) == len(gr4j.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in gr4j.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


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

        streamflow = bucket.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = bucket.init()

        streamflow = bucket.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = bucket.init()

        streamflow = bucket.simulate(
            defaults, sample_precipitation, sample_pet
        )

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
        expected = ["x1", "x2", "x3", "x4", "x5", "x6"]
        assert bucket.param_names == expected


class TestBucketParamDescriptions:
    """Tests for bucket.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(bucket, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(bucket.param_descriptions) == len(bucket.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in bucket.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestCequeauInit:
    """Tests for cequeau.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = cequeau.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 9 elements."""
        defaults, _ = cequeau.init()

        assert len(defaults) == 9

    def test_bounds_shape(self):
        """Bounds should be 9x2 array."""
        _, bounds = cequeau.init()

        assert bounds.shape == (9, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = cequeau.init()

        for i in range(9):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = cequeau.init()

        for i in range(9):
            assert bounds[i, 0] < bounds[i, 1]


class TestCequeauSimulate:
    """Tests for cequeau.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = cequeau.init()

        streamflow = cequeau.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = cequeau.init()

        streamflow = cequeau.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = cequeau.init()

        streamflow = cequeau.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = cequeau.init()
        precip = np.zeros(100)

        streamflow = cequeau.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([100.0, 0.5, 50.0, 3.0])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            cequeau.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = cequeau.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            cequeau.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array(
            [100.0, 100.0, 10.0, 5.0, 500.0, 3.0, 100.0, 100.0, 100.0]
        )

        streamflow = cequeau.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestCequeauParamNames:
    """Tests for cequeau.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(cequeau, "param_names")

    def test_param_names_count(self):
        """Should have 9 parameter names."""
        assert len(cequeau.param_names) == 9

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"]
        assert cequeau.param_names == expected


class TestCequeauParamDescriptions:
    """Tests for cequeau.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(cequeau, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(cequeau.param_descriptions) == len(cequeau.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in cequeau.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestCrecInit:
    """Tests for crec.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = crec.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 6 elements."""
        defaults, _ = crec.init()

        assert len(defaults) == 6

    def test_bounds_shape(self):
        """Bounds should be 6x2 array."""
        _, bounds = crec.init()

        assert bounds.shape == (6, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = crec.init()

        for i in range(6):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = crec.init()

        for i in range(6):
            assert bounds[i, 0] < bounds[i, 1]


class TestCrecSimulate:
    """Tests for crec.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = crec.init()

        streamflow = crec.simulate(defaults, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = crec.init()

        streamflow = crec.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = crec.init()

        streamflow = crec.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = crec.init()
        precip = np.zeros(100)

        streamflow = crec.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([100.0, 0.5, 50.0, 3.0])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            crec.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = crec.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            crec.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([500.0, 500.0, 500.0, 250.0, 500.0, 2.5])

        streamflow = crec.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestCrecParamNames:
    """Tests for crec.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(crec, "param_names")

    def test_param_names_count(self):
        """Should have 6 parameter names."""
        assert len(crec.param_names) == 6

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6"]
        assert crec.param_names == expected


class TestCrecParamDescriptions:
    """Tests for crec.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(crec, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(crec.param_descriptions) == len(crec.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in crec.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestGardeniaInit:
    """Tests for gardenia.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = gardenia.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 6 elements."""
        defaults, _ = gardenia.init()

        assert len(defaults) == 6

    def test_bounds_shape(self):
        """Bounds should be 6x2 array."""
        _, bounds = gardenia.init()

        assert bounds.shape == (6, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = gardenia.init()

        for i in range(6):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = gardenia.init()

        for i in range(6):
            assert bounds[i, 0] < bounds[i, 1]


class TestGardeniaSimulate:
    """Tests for gardenia.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = gardenia.init()

        streamflow = gardenia.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = gardenia.init()

        streamflow = gardenia.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = gardenia.init()

        streamflow = gardenia.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = gardenia.init()
        precip = np.zeros(100)

        streamflow = gardenia.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([100.0, 0.5, 50.0, 3.0])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            gardenia.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = gardenia.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            gardenia.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([500.0, 500.0, 500.0, 250.0, 1.0, 2.5])

        streamflow = gardenia.simulate(
            params, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestGardeniaParamNames:
    """Tests for gardenia.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(gardenia, "param_names")

    def test_param_names_count(self):
        """Should have 6 parameter names."""
        assert len(gardenia.param_names) == 6

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6"]
        assert gardenia.param_names == expected


class TestGardeniaParamDescriptions:
    """Tests for gardenia.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(gardenia, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(gardenia.param_descriptions) == len(gardenia.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in gardenia.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestHymodInit:
    """Tests for hymod.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = hymod.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 6 elements."""
        defaults, _ = hymod.init()

        assert len(defaults) == 6

    def test_bounds_shape(self):
        """Bounds should be 6x2 array."""
        _, bounds = hymod.init()

        assert bounds.shape == (6, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = hymod.init()

        for i in range(6):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = hymod.init()

        for i in range(6):
            assert bounds[i, 0] < bounds[i, 1]


class TestHymodSimulate:
    """Tests for hymod.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = hymod.init()

        streamflow = hymod.simulate(defaults, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = hymod.init()

        streamflow = hymod.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = hymod.init()

        streamflow = hymod.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = hymod.init()
        precip = np.zeros(100)

        streamflow = hymod.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([100.0, 0.5, 50.0, 3.0])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            hymod.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = hymod.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            hymod.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([500.0, 1.0, 0.5, 2.5, 500.0, 5.0])

        streamflow = hymod.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestHymodParamNames:
    """Tests for hymod.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(hymod, "param_names")

    def test_param_names_count(self):
        """Should have 6 parameter names."""
        assert len(hymod.param_names) == 6

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6"]
        assert hymod.param_names == expected


class TestHymodParamDescriptions:
    """Tests for hymod.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(hymod, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(hymod.param_descriptions) == len(hymod.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in hymod.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestHbvInit:
    """Tests for hbv.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = hbv.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 9 elements."""
        defaults, _ = hbv.init()

        assert len(defaults) == 9

    def test_bounds_shape(self):
        """Bounds should be 9x2 array."""
        _, bounds = hbv.init()

        assert bounds.shape == (9, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = hbv.init()

        for i in range(9):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = hbv.init()

        for i in range(9):
            assert bounds[i, 0] < bounds[i, 1]


class TestHbvSimulate:
    """Tests for hbv.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = hbv.init()

        streamflow = hbv.simulate(defaults, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = hbv.init()

        streamflow = hbv.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = hbv.init()

        streamflow = hbv.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = hbv.init()
        precip = np.zeros(100)

        streamflow = hbv.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([500.0, 500.0, 10.0, 50.0])  # only 4 of 9

        with pytest.raises(HolmesValidationError, match="param"):
            hbv.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = hbv.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            hbv.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array(
            [500.0, 500.0, 10.0, 50.0, 10.0, 20.0, 1.0, 50.0, 10.0]
        )

        streamflow = hbv.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestHbvParamNames:
    """Tests for hbv.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(hbv, "param_names")

    def test_param_names_count(self):
        """Should have 9 parameter names."""
        assert len(hbv.param_names) == 9

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"]
        assert hbv.param_names == expected


class TestHbvParamDescriptions:
    """Tests for hbv.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(hbv, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(hbv.param_descriptions) == len(hbv.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in hbv.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestXinanjiangInit:
    """Tests for xinanjiang.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = xinanjiang.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 8 elements."""
        defaults, _ = xinanjiang.init()

        assert len(defaults) == 8

    def test_bounds_shape(self):
        """Bounds should be 8x2 array."""
        _, bounds = xinanjiang.init()

        assert bounds.shape == (8, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = xinanjiang.init()

        for i in range(8):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = xinanjiang.init()

        for i in range(8):
            assert bounds[i, 0] < bounds[i, 1]


class TestXinanjiangSimulate:
    """Tests for xinanjiang.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = xinanjiang.init()

        streamflow = xinanjiang.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = xinanjiang.init()

        streamflow = xinanjiang.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = xinanjiang.init()

        streamflow = xinanjiang.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = xinanjiang.init()
        precip = np.zeros(100)

        streamflow = xinanjiang.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([0.5, 5.0, 10.0, 100.0])  # only 4 of 8

        with pytest.raises(HolmesValidationError, match="param"):
            xinanjiang.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = xinanjiang.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            xinanjiang.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([0.5, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 1.0])

        streamflow = xinanjiang.simulate(
            params, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestXinanjiangParamNames:
    """Tests for xinanjiang.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(xinanjiang, "param_names")

    def test_param_names_count(self):
        """Should have 8 parameter names."""
        assert len(xinanjiang.param_names) == 8

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"]
        assert xinanjiang.param_names == expected


class TestXinanjiangParamDescriptions:
    """Tests for xinanjiang.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(xinanjiang, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(xinanjiang.param_descriptions) == len(
            xinanjiang.param_names
        )

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in xinanjiang.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestSacramentoInit:
    """Tests for sacramento.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = sacramento.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 9 elements."""
        defaults, _ = sacramento.init()

        assert len(defaults) == 9

    def test_bounds_shape(self):
        """Bounds should be 9x2 array."""
        _, bounds = sacramento.init()

        assert bounds.shape == (9, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = sacramento.init()

        for i in range(9):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = sacramento.init()

        for i in range(9):
            assert bounds[i, 0] < bounds[i, 1]


class TestSacramentoSimulate:
    """Tests for sacramento.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = sacramento.init()

        streamflow = sacramento.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = sacramento.init()

        streamflow = sacramento.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = sacramento.init()

        streamflow = sacramento.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = sacramento.init()
        precip = np.zeros(100)

        streamflow = sacramento.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([10.0, 500.0, 250.0, 250.0, 10.0])  # 5 params

        with pytest.raises(HolmesValidationError, match="param"):
            sacramento.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = sacramento.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            sacramento.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array(
            [5.0, 300.0, 100.0, 150.0, 8.0, 20.0, 0.4, 15.0, 3.0]
        )

        streamflow = sacramento.simulate(
            params, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestSacramentoParamNames:
    """Tests for sacramento.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(sacramento, "param_names")

    def test_param_names_count(self):
        """Should have 9 parameter names."""
        assert len(sacramento.param_names) == 9

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"]
        assert sacramento.param_names == expected


class TestSacramentoParamDescriptions:
    """Tests for sacramento.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(sacramento, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(sacramento.param_descriptions) == len(
            sacramento.param_names
        )

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in sacramento.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestPdmInit:
    """Tests for pdm.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = pdm.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 8 elements."""
        defaults, _ = pdm.init()

        assert len(defaults) == 8

    def test_bounds_shape(self):
        """Bounds should be 8x2 array."""
        _, bounds = pdm.init()

        assert bounds.shape == (8, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = pdm.init()

        for i in range(8):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = pdm.init()

        for i in range(8):
            assert bounds[i, 0] < bounds[i, 1]


class TestPdmSimulate:
    """Tests for pdm.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = pdm.init()

        streamflow = pdm.simulate(defaults, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = pdm.init()

        streamflow = pdm.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = pdm.init()

        streamflow = pdm.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = pdm.init()
        precip = np.zeros(100)

        streamflow = pdm.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([10.0, 500.0, 250.0, 250.0, 10.0])  # 5 params

        with pytest.raises(HolmesValidationError, match="param"):
            pdm.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = pdm.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            pdm.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([500.0, 1.0, 0.5, 2.5, 500.0, 10.0, 1.0, 30.0])

        streamflow = pdm.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestPdmParamNames:
    """Tests for pdm.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(pdm, "param_names")

    def test_param_names_count(self):
        """Should have 8 parameter names."""
        assert len(pdm.param_names) == 8

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"]
        assert pdm.param_names == expected


class TestPdmParamDescriptions:
    """Tests for pdm.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(pdm, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(pdm.param_descriptions) == len(pdm.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in pdm.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestHydroModuleIntegration:
    """Integration tests for hydro module."""

    def test_module_structure(self):
        """Hydro module should have correct submodules."""
        from holmes_rs import hydro

        assert hasattr(hydro, "gr4j")
        assert hasattr(hydro, "bucket")
        assert hasattr(hydro, "cequeau")
        assert hasattr(hydro, "crec")
        assert hasattr(hydro, "gardenia")
        assert hasattr(hydro, "hbv")
        assert hasattr(hydro, "hymod")
        assert hasattr(hydro, "ihacres")
        assert hasattr(hydro, "nam")
        assert hasattr(hydro, "pdm")
        assert hasattr(hydro, "sacramento")
        assert hasattr(hydro, "xinanjiang")

    def test_all_models_produce_output(self, sample_precipitation, sample_pet):
        """All models should produce valid streamflow."""
        gr4j_defaults, _ = gr4j.init()
        bucket_defaults, _ = bucket.init()
        cequeau_defaults, _ = cequeau.init()
        crec_defaults, _ = crec.init()
        gardenia_defaults, _ = gardenia.init()
        hbv_defaults, _ = hbv.init()
        hymod_defaults, _ = hymod.init()
        ihacres_defaults, _ = ihacres.init()
        pdm_defaults, _ = pdm.init()
        sacramento_defaults, _ = sacramento.init()
        xinanjiang_defaults, _ = xinanjiang.init()

        gr4j_flow = gr4j.simulate(
            gr4j_defaults, sample_precipitation, sample_pet
        )
        bucket_flow = bucket.simulate(
            bucket_defaults, sample_precipitation, sample_pet
        )
        cequeau_flow = cequeau.simulate(
            cequeau_defaults, sample_precipitation, sample_pet
        )
        crec_flow = crec.simulate(
            crec_defaults, sample_precipitation, sample_pet
        )
        gardenia_flow = gardenia.simulate(
            gardenia_defaults, sample_precipitation, sample_pet
        )
        hbv_flow = hbv.simulate(hbv_defaults, sample_precipitation, sample_pet)
        hymod_flow = hymod.simulate(
            hymod_defaults, sample_precipitation, sample_pet
        )
        ihacres_flow = ihacres.simulate(
            ihacres_defaults, sample_precipitation, sample_pet
        )
        pdm_flow = pdm.simulate(pdm_defaults, sample_precipitation, sample_pet)
        sacramento_flow = sacramento.simulate(
            sacramento_defaults, sample_precipitation, sample_pet
        )
        xinanjiang_flow = xinanjiang.simulate(
            xinanjiang_defaults, sample_precipitation, sample_pet
        )

        assert len(gr4j_flow) == len(sample_precipitation)
        assert len(bucket_flow) == len(sample_precipitation)
        assert len(cequeau_flow) == len(sample_precipitation)
        assert len(crec_flow) == len(sample_precipitation)
        assert len(gardenia_flow) == len(sample_precipitation)
        assert len(hbv_flow) == len(sample_precipitation)
        assert len(hymod_flow) == len(sample_precipitation)
        assert len(ihacres_flow) == len(sample_precipitation)
        assert len(pdm_flow) == len(sample_precipitation)
        assert len(sacramento_flow) == len(sample_precipitation)
        assert len(xinanjiang_flow) == len(sample_precipitation)
        assert np.all(np.isfinite(gr4j_flow))
        assert np.all(np.isfinite(bucket_flow))
        assert np.all(np.isfinite(cequeau_flow))
        assert np.all(np.isfinite(crec_flow))
        assert np.all(np.isfinite(gardenia_flow))
        assert np.all(np.isfinite(hbv_flow))
        assert np.all(np.isfinite(hymod_flow))
        assert np.all(np.isfinite(ihacres_flow))
        assert np.all(np.isfinite(pdm_flow))
        assert np.all(np.isfinite(sacramento_flow))
        assert np.all(np.isfinite(xinanjiang_flow))


class TestIhacresInit:
    """Tests for ihacres.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = ihacres.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 7 elements."""
        defaults, _ = ihacres.init()

        assert len(defaults) == 7

    def test_bounds_shape(self):
        """Bounds should be 7x2 array."""
        _, bounds = ihacres.init()

        assert bounds.shape == (7, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = ihacres.init()

        for i in range(7):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = ihacres.init()

        for i in range(7):
            assert bounds[i, 0] < bounds[i, 1]


class TestIhacresSimulate:
    """Tests for ihacres.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = ihacres.init()

        streamflow = ihacres.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = ihacres.init()

        streamflow = ihacres.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = ihacres.init()

        streamflow = ihacres.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = ihacres.init()
        precip = np.zeros(100)

        streamflow = ihacres.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([100.0, 0.5, 50.0, 3.0])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            ihacres.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = ihacres.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            ihacres.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([500.0, 0.5, 50.0, 500.0, 2.5, 5.0, 5.0])

        streamflow = ihacres.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestIhacresParamNames:
    """Tests for ihacres.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(ihacres, "param_names")

    def test_param_names_count(self):
        """Should have 7 parameter names."""
        assert len(ihacres.param_names) == 7

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        assert ihacres.param_names == expected


class TestIhacresParamDescriptions:
    """Tests for ihacres.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(ihacres, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(ihacres.param_descriptions) == len(ihacres.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in ihacres.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestMartineInit:
    """Tests for martine.init function."""

    def test_returns_tuple(self):
        result = martine.init()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        defaults, _ = martine.init()
        assert len(defaults) == 7

    def test_bounds_shape(self):
        _, bounds = martine.init()
        assert bounds.shape == (7, 2)

    def test_defaults_within_bounds(self):
        defaults, bounds = martine.init()
        for i in range(7):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        _, bounds = martine.init()
        for i in range(7):
            assert bounds[i, 0] < bounds[i, 1]


class TestMartineSimulate:
    """Tests for martine.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        defaults, _ = martine.init()
        streamflow = martine.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        defaults, _ = martine.init()
        streamflow = martine.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        defaults, _ = martine.init()
        streamflow = martine.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        defaults, _ = martine.init()
        precip = np.zeros(100)
        streamflow = martine.simulate(defaults, precip, sample_pet)
        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        wrong_params = np.array([100.0, 25.0, 50.0, 5.0])  # 4 instead of 7
        with pytest.raises(HolmesValidationError, match="param"):
            martine.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        defaults, _ = martine.init()
        short_pet = np.array([2.0, 2.0])
        with pytest.raises(HolmesValidationError, match="length"):
            martine.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        params = np.array([500.0, 500.0, 200.0, 100.0, 0.5, 2.5, 100.0])
        streamflow = martine.simulate(params, sample_precipitation, sample_pet)
        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestMartineParamNames:
    """Tests for martine.param_names constant."""

    def test_param_names_exists(self):
        assert hasattr(martine, "param_names")

    def test_param_names_count(self):
        assert len(martine.param_names) == 7

    def test_param_names_values(self):
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        assert martine.param_names == expected


class TestMartineParamDescriptions:
    """Tests for martine.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        assert hasattr(martine, "param_descriptions")

    def test_param_descriptions_count(self):
        assert len(martine.param_descriptions) == len(martine.param_names)

    def test_param_descriptions_non_empty(self):
        for desc in martine.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestTopmodelInit:
    """Tests for topmodel.init function."""

    def test_returns_tuple(self):
        result = topmodel.init()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        defaults, _ = topmodel.init()
        assert len(defaults) == 7

    def test_bounds_shape(self):
        _, bounds = topmodel.init()
        assert bounds.shape == (7, 2)

    def test_defaults_within_bounds(self):
        defaults, bounds = topmodel.init()
        for i in range(7):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        _, bounds = topmodel.init()
        for i in range(7):
            assert bounds[i, 0] < bounds[i, 1]


class TestTopmodelSimulate:
    """Tests for topmodel.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        defaults, _ = topmodel.init()
        streamflow = topmodel.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        defaults, _ = topmodel.init()
        streamflow = topmodel.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        defaults, _ = topmodel.init()
        streamflow = topmodel.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        defaults, _ = topmodel.init()
        precip = np.zeros(100)
        streamflow = topmodel.simulate(defaults, precip, sample_pet)
        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        wrong_params = np.array([100.0, 25.0, 50.0, 5.0])  # 4 instead of 7
        with pytest.raises(HolmesValidationError, match="param"):
            topmodel.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        defaults, _ = topmodel.init()
        short_pet = np.array([2.0, 2.0])
        with pytest.raises(HolmesValidationError, match="length"):
            topmodel.simulate(defaults, sample_precipitation, short_pet)

    def test_steady_state_constant_forcing(self):
        # P=5, PET=2 with default params should converge to Q≈3 mm/d.
        defaults, _ = topmodel.init()
        precip = np.full(365, 5.0)
        pet = np.full(365, 2.0)
        streamflow = topmodel.simulate(defaults, precip, pet)
        assert np.isclose(streamflow[300:].mean(), 3.0, atol=1e-6)


class TestTopmodelParamNames:
    """Tests for topmodel.param_names constant."""

    def test_param_names_exists(self):
        assert hasattr(topmodel, "param_names")

    def test_param_names_count(self):
        assert len(topmodel.param_names) == 7

    def test_param_names_values(self):
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        assert topmodel.param_names == expected


class TestTopmodelParamDescriptions:
    """Tests for topmodel.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        assert hasattr(topmodel, "param_descriptions")

    def test_param_descriptions_count(self):
        assert len(topmodel.param_descriptions) == len(topmodel.param_names)

    def test_param_descriptions_non_empty(self):
        for desc in topmodel.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestNamInit:
    """Tests for nam.init function."""

    def test_returns_tuple(self):
        result = nam.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        defaults, _ = nam.init()

        assert len(defaults) == 10

    def test_bounds_shape(self):
        _, bounds = nam.init()

        assert bounds.shape == (10, 2)

    def test_defaults_within_bounds(self):
        defaults, bounds = nam.init()

        for i in range(10):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        _, bounds = nam.init()

        for i in range(10):
            assert bounds[i, 0] < bounds[i, 1]


class TestNamSimulate:
    """Tests for nam.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        defaults, _ = nam.init()

        streamflow = nam.simulate(defaults, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        defaults, _ = nam.init()

        streamflow = nam.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        defaults, _ = nam.init()

        streamflow = nam.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        defaults, _ = nam.init()
        precip = np.zeros(100)

        streamflow = nam.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        wrong_params = np.array([100.0, 50.0, 50.0, 3.0])  # 4 instead of 10

        with pytest.raises(HolmesValidationError, match="param"):
            nam.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        defaults, _ = nam.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            nam.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        # Mid-range values, all within bounds.
        params = np.array(
            [100.0, 10.0, 10.0, 2.0, 0.4, 50.0, 200.0, 5.0, 100.0, 1.0]
        )

        streamflow = nam.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestNamParamNames:
    """Tests for nam.param_names constant."""

    def test_param_names_exists(self):
        assert hasattr(nam, "param_names")

    def test_param_names_count(self):
        assert len(nam.param_names) == 10

    def test_param_names_values(self):
        expected = [
            "x1",
            "x2",
            "x3",
            "x4",
            "x5",
            "x6",
            "x7",
            "x8",
            "x9",
            "x10",
        ]
        assert nam.param_names == expected


class TestNamParamDescriptions:
    """Tests for nam.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        assert hasattr(nam, "param_descriptions")

    def test_param_descriptions_count(self):
        assert len(nam.param_descriptions) == len(nam.param_names)

    def test_param_descriptions_non_empty(self):
        for desc in nam.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestMohyseInit:
    """Tests for mohyse.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = mohyse.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 7 elements."""
        defaults, _ = mohyse.init()

        assert len(defaults) == 7

    def test_bounds_shape(self):
        """Bounds should be 7x2 array."""
        _, bounds = mohyse.init()

        assert bounds.shape == (7, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = mohyse.init()

        for i in range(7):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = mohyse.init()

        for i in range(7):
            assert bounds[i, 0] < bounds[i, 1]


class TestMohyseSimulate:
    """Tests for mohyse.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = mohyse.init()

        streamflow = mohyse.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = mohyse.init()

        streamflow = mohyse.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = mohyse.init()

        streamflow = mohyse.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = mohyse.init()
        precip = np.zeros(100)

        streamflow = mohyse.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([0.5, 500.0, 0.1, 0.1])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            mohyse.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = mohyse.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            mohyse.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([0.1, 500.0, 0.1, 0.1, 0.1, 2.0, 2.0])

        streamflow = mohyse.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestMohyseParamNames:
    """Tests for mohyse.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(mohyse, "param_names")

    def test_param_names_count(self):
        """Should have 7 parameter names."""
        assert len(mohyse.param_names) == 7

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        assert mohyse.param_names == expected


class TestMohyseParamDescriptions:
    """Tests for mohyse.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(mohyse, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(mohyse.param_descriptions) == len(mohyse.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in mohyse.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestSmarInit:
    """Tests for smar.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = smar.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 8 elements."""
        defaults, _ = smar.init()

        assert len(defaults) == 8

    def test_bounds_shape(self):
        """Bounds should be 8x2 array."""
        _, bounds = smar.init()

        assert bounds.shape == (8, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = smar.init()

        for i in range(8):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = smar.init()

        for i in range(8):
            assert bounds[i, 0] < bounds[i, 1]


class TestSmarSimulate:
    """Tests for smar.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = smar.init()

        streamflow = smar.simulate(defaults, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = smar.init()

        streamflow = smar.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = smar.init()

        streamflow = smar.simulate(defaults, sample_precipitation, sample_pet)

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = smar.init()
        precip = np.zeros(100)

        streamflow = smar.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([0.5, 5.0, 0.5, 250.0])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            smar.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = smar.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            smar.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([0.5, 5.0, 0.5, 250.0, 100.0, 2.5, 1.0, 0.5])

        streamflow = smar.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestSmarParamNames:
    """Tests for smar.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(smar, "param_names")

    def test_param_names_count(self):
        """Should have 8 parameter names."""
        assert len(smar.param_names) == 8

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"]
        assert smar.param_names == expected


class TestSmarParamDescriptions:
    """Tests for smar.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(smar, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(smar.param_descriptions) == len(smar.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in smar.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestSimhydInit:
    """Tests for simhyd.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = simhyd.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 8 elements."""
        defaults, _ = simhyd.init()

        assert len(defaults) == 8

    def test_bounds_shape(self):
        """Bounds should be 8x2 array."""
        _, bounds = simhyd.init()

        assert bounds.shape == (8, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = simhyd.init()

        for i in range(8):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = simhyd.init()

        for i in range(8):
            assert bounds[i, 0] < bounds[i, 1]


class TestSimhydSimulate:
    """Tests for simhyd.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = simhyd.init()

        streamflow = simhyd.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = simhyd.init()

        streamflow = simhyd.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = simhyd.init()

        streamflow = simhyd.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = simhyd.init()
        precip = np.zeros(100)

        streamflow = simhyd.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([5.0, 250.0, 500.0, 2.5])  # Only 4 params

        with pytest.raises(HolmesValidationError, match="param"):
            simhyd.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = simhyd.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            simhyd.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([5.0, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 250.0])

        streamflow = simhyd.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestSimhydParamNames:
    """Tests for simhyd.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(simhyd, "param_names")

    def test_param_names_count(self):
        """Should have 8 parameter names."""
        assert len(simhyd.param_names) == 8

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"]
        assert simhyd.param_names == expected


class TestSimhydParamDescriptions:
    """Tests for simhyd.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(simhyd, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(simhyd.param_descriptions) == len(simhyd.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in simhyd.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestMordorInit:
    """Tests for mordor.init function."""

    def test_returns_tuple(self):
        """init should return a tuple of (defaults, bounds)."""
        result = mordor.init()

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        """Default parameters should have 6 elements."""
        defaults, _ = mordor.init()

        assert len(defaults) == 6

    def test_bounds_shape(self):
        """Bounds should be 6x2 array."""
        _, bounds = mordor.init()

        assert bounds.shape == (6, 2)

    def test_defaults_within_bounds(self):
        """Default values should be within bounds."""
        defaults, bounds = mordor.init()

        for i in range(6):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        """Lower bounds should be less than upper bounds."""
        _, bounds = mordor.init()

        for i in range(6):
            assert bounds[i, 0] < bounds[i, 1]


class TestMordorSimulate:
    """Tests for mordor.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        """Output should have same length as input."""
        defaults, _ = mordor.init()

        streamflow = mordor.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        """All streamflow values should be non-negative."""
        defaults, _ = mordor.init()

        streamflow = mordor.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        """All output values should be finite."""
        defaults, _ = mordor.init()

        streamflow = mordor.simulate(
            defaults, sample_precipitation, sample_pet
        )

        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        """Should handle zero precipitation."""
        defaults, _ = mordor.init()
        precip = np.zeros(100)

        streamflow = mordor.simulate(defaults, precip, sample_pet)

        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        """Should raise error for wrong parameter count."""
        wrong_params = np.array([1.0, 100.0, 5.0, 2.0])

        with pytest.raises(HolmesValidationError, match="param"):
            mordor.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        """Should raise error for mismatched input lengths."""
        defaults, _ = mordor.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            mordor.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        """Should work with custom parameter values."""
        params = np.array([1.0, 100.0, 5.0, 2.0, 200.0, 300.0])

        streamflow = mordor.simulate(params, sample_precipitation, sample_pet)

        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestMordorParamNames:
    """Tests for mordor.param_names constant."""

    def test_param_names_exists(self):
        """param_names should be accessible."""
        assert hasattr(mordor, "param_names")

    def test_param_names_count(self):
        """Should have 6 parameter names."""
        assert len(mordor.param_names) == 6

    def test_param_names_values(self):
        """Parameter names should match expected values."""
        expected = ["x1", "x2", "x3", "x4", "x5", "x6"]
        assert mordor.param_names == expected


class TestMordorParamDescriptions:
    """Tests for mordor.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        """param_descriptions should be accessible."""
        assert hasattr(mordor, "param_descriptions")

    def test_param_descriptions_count(self):
        """Should have same count as param_names."""
        assert len(mordor.param_descriptions) == len(mordor.param_names)

    def test_param_descriptions_non_empty(self):
        """All descriptions should be non-empty strings."""
        for desc in mordor.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestWageningenInit:
    """Tests for wageningen.init function."""

    def test_returns_tuple(self):
        result = wageningen.init()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        defaults, _ = wageningen.init()
        assert len(defaults) == 8

    def test_bounds_shape(self):
        _, bounds = wageningen.init()
        assert bounds.shape == (8, 2)

    def test_defaults_within_bounds(self):
        defaults, bounds = wageningen.init()
        for i in range(8):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        _, bounds = wageningen.init()
        for i in range(8):
            assert bounds[i, 0] < bounds[i, 1]


class TestWageningenSimulate:
    """Tests for wageningen.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        defaults, _ = wageningen.init()
        streamflow = wageningen.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        defaults, _ = wageningen.init()
        streamflow = wageningen.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        defaults, _ = wageningen.init()
        streamflow = wageningen.simulate(
            defaults, sample_precipitation, sample_pet
        )
        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        defaults, _ = wageningen.init()
        precip = np.zeros(100)
        streamflow = wageningen.simulate(defaults, precip, sample_pet)
        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        wrong_params = np.array([100.0, 500.0, 100.0, 100.0])

        with pytest.raises(HolmesValidationError, match="param"):
            wageningen.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        defaults, _ = wageningen.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            wageningen.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        params = np.array([100.0, 500.0, 100.0, 100.0, 50.0, 3.0, 5.0, 1.0])
        streamflow = wageningen.simulate(
            params, sample_precipitation, sample_pet
        )
        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestWageningenParamNames:
    """Tests for wageningen.param_names constant."""

    def test_param_names_exists(self):
        assert hasattr(wageningen, "param_names")

    def test_param_names_count(self):
        assert len(wageningen.param_names) == 8

    def test_param_names_values(self):
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"]
        assert wageningen.param_names == expected


class TestWageningenParamDescriptions:
    """Tests for wageningen.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        assert hasattr(wageningen, "param_descriptions")

    def test_param_descriptions_count(self):
        assert len(wageningen.param_descriptions) == len(
            wageningen.param_names
        )

    def test_param_descriptions_non_empty(self):
        for desc in wageningen.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestTankInit:
    """Tests for tank.init function."""

    def test_returns_tuple(self):
        result = tank.init()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_defaults_shape(self):
        defaults, _ = tank.init()
        assert len(defaults) == 7

    def test_bounds_shape(self):
        _, bounds = tank.init()
        assert bounds.shape == (7, 2)

    def test_defaults_within_bounds(self):
        defaults, bounds = tank.init()
        for i in range(7):
            assert bounds[i, 0] <= defaults[i] <= bounds[i, 1]

    def test_bounds_ordered(self):
        _, bounds = tank.init()
        for i in range(7):
            assert bounds[i, 0] < bounds[i, 1]


class TestTankSimulate:
    """Tests for tank.simulate function."""

    def test_output_length(self, sample_precipitation, sample_pet):
        defaults, _ = tank.init()
        streamflow = tank.simulate(defaults, sample_precipitation, sample_pet)
        assert len(streamflow) == len(sample_precipitation)

    def test_nonnegative_streamflow(self, sample_precipitation, sample_pet):
        defaults, _ = tank.init()
        streamflow = tank.simulate(defaults, sample_precipitation, sample_pet)
        assert np.all(streamflow >= 0)

    def test_finite_output(self, sample_precipitation, sample_pet):
        defaults, _ = tank.init()
        streamflow = tank.simulate(defaults, sample_precipitation, sample_pet)
        assert np.all(np.isfinite(streamflow))

    def test_zero_precipitation(self, sample_pet):
        defaults, _ = tank.init()
        precip = np.zeros(100)
        streamflow = tank.simulate(defaults, precip, sample_pet)
        assert len(streamflow) == 100
        assert np.all(np.isfinite(streamflow))

    def test_param_count_error(self, sample_precipitation, sample_pet):
        wrong_params = np.array([10.0, 5.0, 2.0, 3.0])

        with pytest.raises(HolmesValidationError, match="param"):
            tank.simulate(wrong_params, sample_precipitation, sample_pet)

    def test_length_mismatch_error(self, sample_precipitation):
        defaults, _ = tank.init()
        short_pet = np.array([2.0, 2.0])

        with pytest.raises(HolmesValidationError, match="length"):
            tank.simulate(defaults, sample_precipitation, short_pet)

    def test_custom_params(self, sample_precipitation, sample_pet):
        params = np.array([100.0, 20.0, 10.0, 5.0, 2.5, 1.0, 5.0])
        streamflow = tank.simulate(params, sample_precipitation, sample_pet)
        assert len(streamflow) == len(sample_precipitation)
        assert np.all(np.isfinite(streamflow))


class TestTankParamNames:
    """Tests for tank.param_names constant."""

    def test_param_names_exists(self):
        assert hasattr(tank, "param_names")

    def test_param_names_count(self):
        assert len(tank.param_names) == 7

    def test_param_names_values(self):
        expected = ["x1", "x2", "x3", "x4", "x5", "x6", "x7"]
        assert tank.param_names == expected


class TestTankParamDescriptions:
    """Tests for tank.param_descriptions constant."""

    def test_param_descriptions_exists(self):
        assert hasattr(tank, "param_descriptions")

    def test_param_descriptions_count(self):
        assert len(tank.param_descriptions) == len(tank.param_names)

    def test_param_descriptions_non_empty(self):
        for desc in tank.param_descriptions:
            assert isinstance(desc, str)
            assert len(desc) > 0
