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

    def test_get_config_crec(self):
        """CREC parameter config has expected structure."""
        config = hydro.get_config("crec")
        assert isinstance(config, list)
        assert len(config) == 6
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

    def test_crec_param_names(self):
        """CREC has expected parameter names."""
        config = hydro.get_config("crec")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4", "x5", "x6"]

    def test_get_config_gardenia(self):
        """GARDENIA parameter config has expected structure."""
        config = hydro.get_config("gardenia")
        assert isinstance(config, list)
        assert len(config) == 6
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param
            assert "description" in param

    def test_gardenia_param_names(self):
        """GARDENIA has expected parameter names."""
        config = hydro.get_config("gardenia")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4", "x5", "x6"]

    def test_get_config_hymod(self):
        """HYMOD parameter config has expected structure."""
        config = hydro.get_config("hymod")
        assert isinstance(config, list)
        assert len(config) == 6
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param
            assert "description" in param

    def test_hymod_param_names(self):
        """HYMOD has expected parameter names."""
        config = hydro.get_config("hymod")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4", "x5", "x6"]

    def test_get_config_hbv(self):
        """HBV parameter config has expected structure."""
        config = hydro.get_config("hbv")
        assert isinstance(config, list)
        assert len(config) == 9
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param
            assert "description" in param

    def test_hbv_param_names(self):
        """HBV has expected parameter names."""
        config = hydro.get_config("hbv")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"]

    def test_get_config_xinanjiang(self):
        """XINANJIANG parameter config has expected structure."""
        config = hydro.get_config("xinanjiang")
        assert isinstance(config, list)
        assert len(config) == 8
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param
            assert "description" in param

    def test_xinanjiang_param_names(self):
        """XINANJIANG has expected parameter names."""
        config = hydro.get_config("xinanjiang")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"]

    def test_get_config_sacramento(self):
        """SACRAMENTO parameter config has expected structure."""
        config = hydro.get_config("sacramento")
        assert isinstance(config, list)
        assert len(config) == 9
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param
            assert "description" in param

    def test_sacramento_param_names(self):
        """SACRAMENTO has expected parameter names."""
        config = hydro.get_config("sacramento")
        names = [p["name"] for p in config]
        assert names == [
            "x1",
            "x2",
            "x3",
            "x4",
            "x5",
            "x6",
            "x7",
            "x8",
            "x9",
        ]

    def test_descriptions_are_non_empty_strings(self):
        """All parameters have a non-empty string description."""
        for model in (
            "gr4j",
            "bucket",
            "cequeau",
            "crec",
            "gardenia",
            "hbv",
            "hymod",
            "sacramento",
            "xinanjiang",
        ):
            config = hydro.get_config(model)
            for param in config:
                assert isinstance(param["description"], str), (
                    f"{model} param {param['name']} description is not a string"
                )
                assert len(param["description"]) > 0, (
                    f"{model} param {param['name']} has empty description"
                )

    def test_defaults_within_bounds(self):
        """Default values are within min/max bounds."""
        for model in (
            "gr4j",
            "bucket",
            "cequeau",
            "crec",
            "gardenia",
            "hbv",
            "hymod",
            "sacramento",
            "xinanjiang",
        ):
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

    def test_get_model_crec(self):
        """Returns CREC simulate function."""
        simulate = hydro.get_model("crec")
        assert callable(simulate)

    def test_get_model_gardenia(self):
        """Returns GARDENIA simulate function."""
        simulate = hydro.get_model("gardenia")
        assert callable(simulate)

    def test_gardenia_simulate(self):
        """GARDENIA simulate produces output."""
        simulate = hydro.get_model("gardenia")
        config = hydro.get_config("gardenia")
        params = np.array([p["default"] for p in config])
        n = 365
        precipitation = np.random.uniform(0, 20, n)
        pet = np.random.uniform(0, 5, n)
        result = simulate(params, precipitation, pet)
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)

    def test_get_model_hymod(self):
        """Returns HYMOD simulate function."""
        simulate = hydro.get_model("hymod")
        assert callable(simulate)

    def test_hymod_simulate(self):
        """HYMOD simulate produces output."""
        simulate = hydro.get_model("hymod")
        config = hydro.get_config("hymod")
        params = np.array([p["default"] for p in config])
        n = 365
        precipitation = np.random.uniform(0, 20, n)
        pet = np.random.uniform(0, 5, n)
        result = simulate(params, precipitation, pet)
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)

    def test_get_model_hbv(self):
        """Returns HBV simulate function."""
        simulate = hydro.get_model("hbv")
        assert callable(simulate)

    def test_hbv_simulate(self):
        """HBV simulate produces output."""
        simulate = hydro.get_model("hbv")
        config = hydro.get_config("hbv")
        params = np.array([p["default"] for p in config])
        n = 365
        precipitation = np.random.uniform(0, 20, n)
        pet = np.random.uniform(0, 5, n)
        result = simulate(params, precipitation, pet)
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)

    def test_crec_simulate(self):
        """CREC simulate produces output."""
        simulate = hydro.get_model("crec")
        config = hydro.get_config("crec")
        params = np.array([p["default"] for p in config])
        n = 365
        precipitation = np.random.uniform(0, 20, n)
        pet = np.random.uniform(0, 5, n)
        result = simulate(params, precipitation, pet)
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)

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

    def test_get_model_xinanjiang(self):
        """Returns XINANJIANG simulate function."""
        simulate = hydro.get_model("xinanjiang")
        assert callable(simulate)

    def test_xinanjiang_simulate(self):
        """XINANJIANG simulate produces output."""
        simulate = hydro.get_model("xinanjiang")
        config = hydro.get_config("xinanjiang")
        params = np.array([p["default"] for p in config])
        n = 365
        precipitation = np.random.uniform(0, 20, n)
        pet = np.random.uniform(0, 5, n)
        result = simulate(params, precipitation, pet)
        assert isinstance(result, np.ndarray)
        assert len(result) == n
        assert np.all(result >= 0)

    def test_get_model_sacramento(self):
        """Returns SACRAMENTO simulate function."""
        simulate = hydro.get_model("sacramento")
        assert callable(simulate)

    def test_sacramento_simulate(self):
        """SACRAMENTO simulate produces output."""
        simulate = hydro.get_model("sacramento")
        config = hydro.get_config("sacramento")
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
    def test_crec_output_length_matches_input(self, precipitation):
        """CREC output length matches input length."""
        simulate = hydro.get_model("crec")
        config = hydro.get_config("crec")
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
    def test_crec_output_non_negative(self, precipitation):
        """CREC output is non-negative."""
        simulate = hydro.get_model("crec")
        config = hydro.get_config("crec")
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
    def test_gardenia_output_length_matches_input(self, precipitation):
        """GARDENIA output length matches input length."""
        simulate = hydro.get_model("gardenia")
        config = hydro.get_config("gardenia")
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
    def test_gardenia_output_non_negative(self, precipitation):
        """GARDENIA output is non-negative."""
        simulate = hydro.get_model("gardenia")
        config = hydro.get_config("gardenia")
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

    @given(
        st.lists(
            st.floats(min_value=0.0, max_value=50.0, allow_nan=False),
            min_size=100,
            max_size=500,
        )
    )
    @settings(max_examples=20)
    def test_hymod_output_length_matches_input(self, precipitation):
        """HYMOD output length matches input length."""
        simulate = hydro.get_model("hymod")
        config = hydro.get_config("hymod")
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
    def test_hymod_output_non_negative(self, precipitation):
        """HYMOD output is non-negative."""
        simulate = hydro.get_model("hymod")
        config = hydro.get_config("hymod")
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
    def test_hbv_output_length_matches_input(self, precipitation):
        """HBV output length matches input length."""
        simulate = hydro.get_model("hbv")
        config = hydro.get_config("hbv")
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
    def test_hbv_output_non_negative(self, precipitation):
        """HBV output is non-negative."""
        simulate = hydro.get_model("hbv")
        config = hydro.get_config("hbv")
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
    def test_xinanjiang_output_length_matches_input(self, precipitation):
        """XINANJIANG output length matches input length."""
        simulate = hydro.get_model("xinanjiang")
        config = hydro.get_config("xinanjiang")
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
    def test_xinanjiang_output_non_negative(self, precipitation):
        """XINANJIANG output is non-negative."""
        simulate = hydro.get_model("xinanjiang")
        config = hydro.get_config("xinanjiang")
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
    def test_sacramento_output_length_matches_input(self, precipitation):
        """SACRAMENTO output length matches input length."""
        simulate = hydro.get_model("sacramento")
        config = hydro.get_config("sacramento")
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
    def test_sacramento_output_non_negative(self, precipitation):
        """SACRAMENTO output is non-negative."""
        simulate = hydro.get_model("sacramento")
        config = hydro.get_config("sacramento")
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

    def test_get_config_crec_numerical_error(self):
        """get_config handles HolmesNumericalError for CREC."""
        with patch(
            "holmes_rs.hydro.crec.init",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            with pytest.raises(HolmesNumericalError):
                hydro.get_config("crec")

    def test_simulate_crec_numerical_error(self):
        """CREC simulate handles HolmesNumericalError from Rust."""
        with patch(
            "holmes.models.hydro.crec.simulate",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            simulate = hydro.get_model("crec")
            with pytest.raises(HolmesNumericalError):
                params = np.array([500.0, 500.0, 500.0, 250.0, 500.0, 2.5])
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_simulate_crec_validation_error(self):
        """CREC simulate handles HolmesValidationError from Rust."""
        with patch(
            "holmes.models.hydro.crec.simulate",
            side_effect=HolmesValidationError("Validation error"),
        ):
            simulate = hydro.get_model("crec")
            with pytest.raises(HolmesValidationError):
                params = np.array([500.0, 500.0, 500.0, 250.0, 500.0, 2.5])
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_get_config_gardenia_numerical_error(self):
        """get_config handles HolmesNumericalError for GARDENIA."""
        with patch(
            "holmes_rs.hydro.gardenia.init",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            with pytest.raises(HolmesNumericalError):
                hydro.get_config("gardenia")

    def test_simulate_gardenia_numerical_error(self):
        """GARDENIA simulate handles HolmesNumericalError from Rust."""
        with patch(
            "holmes.models.hydro.gardenia.simulate",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            simulate = hydro.get_model("gardenia")
            with pytest.raises(HolmesNumericalError):
                params = np.array([500.0, 500.0, 500.0, 250.0, 1.0, 2.5])
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_simulate_gardenia_validation_error(self):
        """GARDENIA simulate handles HolmesValidationError from Rust."""
        with patch(
            "holmes.models.hydro.gardenia.simulate",
            side_effect=HolmesValidationError("Validation error"),
        ):
            simulate = hydro.get_model("gardenia")
            with pytest.raises(HolmesValidationError):
                params = np.array([500.0, 500.0, 500.0, 250.0, 1.0, 2.5])
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_get_config_hymod_numerical_error(self):
        """get_config handles HolmesNumericalError for HYMOD."""
        with patch(
            "holmes_rs.hydro.hymod.init",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            with pytest.raises(HolmesNumericalError):
                hydro.get_config("hymod")

    def test_simulate_hymod_numerical_error(self):
        """HYMOD simulate handles HolmesNumericalError from Rust."""
        with patch(
            "holmes.models.hydro.hymod.simulate",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            simulate = hydro.get_model("hymod")
            with pytest.raises(HolmesNumericalError):
                params = np.array([500.0, 1.0, 0.5, 2.5, 500.0, 5.0])
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_simulate_hymod_validation_error(self):
        """HYMOD simulate handles HolmesValidationError from Rust."""
        with patch(
            "holmes.models.hydro.hymod.simulate",
            side_effect=HolmesValidationError("Validation error"),
        ):
            simulate = hydro.get_model("hymod")
            with pytest.raises(HolmesValidationError):
                params = np.array([500.0, 1.0, 0.5, 2.5, 500.0, 5.0])
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_get_config_hbv_numerical_error(self):
        """get_config handles HolmesNumericalError for HBV."""
        with patch(
            "holmes_rs.hydro.hbv.init",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            with pytest.raises(HolmesNumericalError):
                hydro.get_config("hbv")

    def test_simulate_hbv_numerical_error(self):
        """HBV simulate handles HolmesNumericalError from Rust."""
        with patch(
            "holmes.models.hydro.hbv.simulate",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            simulate = hydro.get_model("hbv")
            with pytest.raises(HolmesNumericalError):
                params = np.array(
                    [500.0, 500.0, 10.0, 50.0, 10.0, 20.0, 1.0, 50.0, 10.0]
                )
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_simulate_hbv_validation_error(self):
        """HBV simulate handles HolmesValidationError from Rust."""
        with patch(
            "holmes.models.hydro.hbv.simulate",
            side_effect=HolmesValidationError("Validation error"),
        ):
            simulate = hydro.get_model("hbv")
            with pytest.raises(HolmesValidationError):
                params = np.array(
                    [500.0, 500.0, 10.0, 50.0, 10.0, 20.0, 1.0, 50.0, 10.0]
                )
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_get_config_xinanjiang_numerical_error(self):
        """get_config handles HolmesNumericalError for XINANJIANG."""
        with patch(
            "holmes_rs.hydro.xinanjiang.init",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            with pytest.raises(HolmesNumericalError):
                hydro.get_config("xinanjiang")

    def test_simulate_xinanjiang_numerical_error(self):
        """XINANJIANG simulate handles HolmesNumericalError from Rust."""
        with patch(
            "holmes.models.hydro.xinanjiang.simulate",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            simulate = hydro.get_model("xinanjiang")
            with pytest.raises(HolmesNumericalError):
                params = np.array(
                    [0.5, 10.0, 25.0, 250.0, 1000.0, 5.0, 25.0, 2.5]
                )
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_simulate_xinanjiang_validation_error(self):
        """XINANJIANG simulate handles HolmesValidationError from Rust."""
        with patch(
            "holmes.models.hydro.xinanjiang.simulate",
            side_effect=HolmesValidationError("Validation error"),
        ):
            simulate = hydro.get_model("xinanjiang")
            with pytest.raises(HolmesValidationError):
                params = np.array(
                    [0.5, 10.0, 25.0, 250.0, 1000.0, 5.0, 25.0, 2.5]
                )
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_get_config_sacramento_numerical_error(self):
        """get_config handles HolmesNumericalError for SACRAMENTO."""
        with patch(
            "holmes_rs.hydro.sacramento.init",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            with pytest.raises(HolmesNumericalError):
                hydro.get_config("sacramento")

    def test_simulate_sacramento_numerical_error(self):
        """SACRAMENTO simulate handles HolmesNumericalError from Rust."""
        with patch(
            "holmes.models.hydro.sacramento.simulate",
            side_effect=HolmesNumericalError("Numerical error"),
        ):
            simulate = hydro.get_model("sacramento")
            with pytest.raises(HolmesNumericalError):
                params = np.array(
                    [10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.5, 25.0, 5.0]
                )
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)

    def test_simulate_sacramento_validation_error(self):
        """SACRAMENTO simulate handles HolmesValidationError from Rust."""
        with patch(
            "holmes.models.hydro.sacramento.simulate",
            side_effect=HolmesValidationError("Validation error"),
        ):
            simulate = hydro.get_model("sacramento")
            with pytest.raises(HolmesValidationError):
                params = np.array(
                    [10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.5, 25.0, 5.0]
                )
                precip = np.array([10.0, 20.0, 15.0])
                pet = np.array([2.0, 3.0, 2.5])
                simulate(params, precip, pet)
