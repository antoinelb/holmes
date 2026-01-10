"""Unit tests for holmes.models.hydro module."""

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

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

    def test_get_config_bucket(self):
        """Bucket parameter config has expected structure."""
        config = hydro.get_config("bucket")
        assert isinstance(config, list)
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param
            assert "max" in param

    def test_gr4j_param_names(self):
        """GR4J has expected parameter names."""
        config = hydro.get_config("gr4j")
        names = [p["name"] for p in config]
        assert names == ["x1", "x2", "x3", "x4"]

    def test_bucket_param_names(self):
        """Bucket has expected parameter names."""
        config = hydro.get_config("bucket")
        names = [p["name"] for p in config]
        assert names == ["c_soil", "alpha", "k_r", "delta", "beta", "k_t"]

    def test_defaults_within_bounds(self):
        """Default values are within min/max bounds."""
        for model in ["gr4j", "bucket"]:
            config = hydro.get_config(model)
            for param in config:
                assert param["min"] <= param["default"] <= param["max"]


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
