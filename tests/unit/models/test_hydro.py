"""Unit tests for holmes.models.hydro module."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import patch

from holmes.exceptions import HolmesNumericalError, HolmesValidationError
from holmes.models import hydro


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_gr4j(self):
        """GR4J parameter config has expected structure."""
        config = hydro.get_config("gr4j")
        assert isinstance(config, list)
        assert len(config) == 4  # GR4J has 4 parameters
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param
            assert "description" in param

    def test_get_config_bucket(self):
        """Bucket parameter config has expected structure."""
        config = hydro.get_config("bucket")
        assert isinstance(config, list)
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param
            assert "description" in param

    def test_get_config_cequeau(self):
        """CEQUEAU parameter config has expected structure."""
        config = hydro.get_config("cequeau")
        assert isinstance(config, list)
        assert len(config) == 9
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param
            assert "description" in param

    def test_gr4j_param_names(self):
        """GR4J has expected parameter names."""
        config = hydro.get_config("gr4j")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4"]

    def test_bucket_param_names(self):
        """Bucket has expected parameter names."""
        config = hydro.get_config("bucket")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4", "x5", "x6"]

    def test_cequeau_param_names(self):
        """CEQUEAU has expected parameter names."""
        config = hydro.get_config("cequeau")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"]

    def test_descriptions_are_non_empty_strings(self):
        """All parameters have a non-empty string description."""
        for model in ("gr4j", "bucket", "cequeau"):
            config = hydro.get_config(model)
            for param in config:
                assert isinstance(
                    param["description"], str
                ), f"{model} param {param['name']} description is not a string"
                assert (
                    len(param["description"]) > 0
                ), f"{model} param {param['name']} has empty description"

    def test_defaults_within_bounds(self):
        """Default values are within min/max bounds."""
        for model in ("gr4j", "bucket", "cequeau"):
            config = hydro.get_config(model)
            for param in config:
                min_val = float(param["min"])
                default_val = float(param["default"])
                max_val = float(param["max"])
                assert min_val <= default_val <= max_val


class TestGetModel:
    """Tests for get_model function."""

    def test_get_model_gr4j(self):
        """Returns GR4J simulate function."""
        simulate = hydro.get_model("gr4j")
        assert callable(simulate)

    def test_get_model_bucket(self):
        """Returns bucket simulate function."""
        simulate = hydro.get_model("bucket")
        assert callable(simulate)

    def test_gr4j_simulate(self):
        """GR4J simulate produces output."""
        simulate = hydro.get_model("gr4j")
        config = hydro.get_config("gr4j")
        params = np.array([p["default"] for p in config])
        n = 365
        precipitation = np.random.uniform(0, 20, n)
        pet = np.random.uniform(0, 5, n)
        result = simulate(params, precipitation, pet)
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)

    def test_bucket_simulate(self):
        """Bucket simulate produces output."""
        simulate = hydro.get_model("bucket")
        config = hydro.get_config("bucket")
        params = np.array([p["default"] for p in config])
        n = 365
        precipitation = np.random.uniform(0, 20, n)
        pet = np.random.uniform(0, 5, n)
        result = simulate(params, precipitation, pet)
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)

    def test_get_model_cequeau(self):
        """Returns CEQUEAU simulate function."""
        simulate = hydro.get_model("cequeau")
        assert callable(simulate)

    def test_cequeau_simulate(self):
        """CEQUEAU simulate produces output."""
        simulate = hydro.get_model("cequeau")
        config = hydro.get_config("cequeau")
        params = np.array([p["default"] for p in config])
        n = 365
        precipitation = np.random.uniform(0, 20, n)
        pet = np.random.uniform(0, 5, n)
        result = simulate(params, precipitation, pet)
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)


class TestHypothesis:
    """Property-based tests for hydro models."""

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=20)
    def test_gr4j_output_length_matches_input(self, precipitation):
        """GR4J output length matches input length."""
        simulate = hydro.get_model("gr4j")
        config = hydro.get_config("gr4j")
        params = np.array([p["default"] for p in config])
        precip = np.array(precipitation)
        pet = np.random.uniform(0, 5, len(precipitation))
        result = simulate(params, precip, pet)
        assert len(result) == len(precipitation)

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=20)
    def test_bucket_output_length_matches_input(self, precipitation):
        """Bucket output length matches input length."""
        simulate = hydro.get_model("bucket")
        config = hydro.get_config("bucket")
        params = np.array([p["default"] for p in config])
        precip = np.array(precipitation)
        pet = np.random.uniform(0, 5, len(precipitation))
        result = simulate(params, precip, pet)
        assert len(result) == len(precipitation)

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=20)
    def test_gr4j_output_non_negative(self, precipitation):
        """GR4J output is non-negative."""
        simulate = hydro.get_model("gr4j")
        config = hydro.get_config("gr4j")
        params = np.array([p["default"] for p in config])
        precip = np.array(precipitation)
        pet = np.random.uniform(0, 5, len(precipitation))
        result = simulate(params, precip, pet)
        assert np.all(result >= 0)

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=20)
    def test_bucket_output_non_negative(self, precipitation):
        """Bucket output is non-negative."""
        simulate = hydro.get_model("bucket")
        config = hydro.get_config("bucket")
        params = np.array([p["default"] for p in config])
        precip = np.array(precipitation)
        pet = np.random.uniform(0, 5, len(precipitation))
        result = simulate(params, precip, pet)
        assert np.all(result >= 0)

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=20)
    def test_cequeau_output_length_matches_input(self, precipitation):
        """CEQUEAU output length matches input length."""
        simulate = hydro.get_model("cequeau")
        config = hydro.get_config("cequeau")
        params = np.array([p["default"] for p in config])
        precip = np.array(precipitation)
        pet = np.random.uniform(0, 5, len(precipitation))
        result = simulate(params, precip, pet)
        assert len(result) == len(precipitation)

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=20)
    def test_cequeau_output_non_negative(self, precipitation):
        """CEQUEAU output is non-negative."""
        simulate = hydro.get_model("cequeau")
        config = hydro.get_config("cequeau")
        params = np.array([p["default"] for p in config])
        precip = np.array(precipitation)
        pet = np.random.uniform(0, 5, len(precipitation))
        result = simulate(params, precip, pet)
        assert np.all(result >= 0)


class TestErrorHandling:
    """Tests for error handling in hydro models."""

    def test_get_config_numerical_error(self):
        """get_config handles HolmesNumericalError from Rust."""
        with patch(
            "holmes_rs.hydro.gr4j.init",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            with pytest.raises(HolmesNumericalError):
                hydro.get_config("gr4j")

    def test_get_config_validation_error(self):
        """get_config handles HolmesValidationError from Rust."""
        with patch(
            "holmes_rs.hydro.bucket.init",
            side_effect=HolmesValidationError("Validation error"),
        ):
            with pytest.raises(HolmesValidationError):
                hydro.get_config("bucket")

    def test_simulate_numerical_error(self):
        """Simulate handles HolmesNumericalError from Rust."""
        # Patch before get_model to capture the mock in the closure
        with patch(
            "holmes.models.hydro.gr4j.simulate",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            simulate = hydro.get_model("gr4j")
            with pytest.raises(HolmesNumericalError):
                params = np.array([100.0, 0.0, 50.0, 2.0])
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_simulate_validation_error(self):
        """Simulate handles HolmesValidationError from Rust."""
        # Patch before get_model to capture the mock in the closure
        with patch(
            "holmes.models.hydro.bucket.simulate",
            side_effect=HolmesValidationError("Validation error"),
        ):
            simulate = hydro.get_model("bucket")
            with pytest.raises(HolmesValidationError):
                params = np.array([100.0, 0.5, 100.0, 6.0, 0.5, 200.0])
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_get_config_cequeau_numerical_error(self):
        """get_config handles HolmesNumericalError for CEQUEAU."""
        with patch(
            "holmes_rs.hydro.cequeau.init",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            with pytest.raises(HolmesNumericalError):
                hydro.get_config("cequeau")

    def test_simulate_cequeau_numerical_error(self):
        """CEQUEAU simulate handles HolmesNumericalError from Rust."""
        with patch(
            "holmes.models.hydro.cequeau.simulate",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            simulate = hydro.get_model("cequeau")
            with pytest.raises(HolmesNumericalError):
                params = np.array(
                    [65.0, 65.0, 6.0, 2.0, 30.0, 5.0, 50.0, 50.0, 50.0]
                )
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_simulate_cequeau_validation_error(self):
        """CEQUEAU simulate handles HolmesValidationError from Rust."""
        with patch(
            "holmes.models.hydro.cequeau.simulate",
            side_effect=HolmesValidationError("Validation error"),
        ):
            simulate = hydro.get_model("cequeau")
            with pytest.raises(HolmesValidationError):
                params = np.array(
                    [65.0, 65.0, 6.0, 2.0, 30.0, 5.0, 50.0, 50.0, 50.0]
                )
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)
