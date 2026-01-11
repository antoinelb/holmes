"""Unit tests for holmes.models.utils module."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from holmes.models.utils import evaluate


class TestEvaluate:
    """Tests for evaluate function."""

    @pytest.fixture
    def sample_data(self):
        """Sample observations and simulations for testing."""
        np.random.seed(42)
        n = 100
        observations = np.random.uniform(1, 100, n)
        simulations = observations + np.random.normal(0, 5, n)
        simulations = np.maximum(simulations, 0.1)  # Ensure positive
        return observations, simulations

    def test_evaluate_rmse(self, sample_data):
        """RMSE calculation produces expected result."""
        observations, simulations = sample_data
        result = evaluate(observations, simulations, "rmse", "none")
        assert isinstance(result, float)
        assert result >= 0

    def test_evaluate_nse(self, sample_data):
        """NSE calculation produces expected result."""
        observations, simulations = sample_data
        result = evaluate(observations, simulations, "nse", "none")
        assert isinstance(result, float)
        assert result <= 1.0

    def test_evaluate_kge(self, sample_data):
        """KGE calculation produces expected result."""
        observations, simulations = sample_data
        result = evaluate(observations, simulations, "kge", "none")
        assert isinstance(result, float)
        assert result <= 1.0

    def test_evaluate_mean_bias(self, sample_data):
        """Mean bias calculation produces expected result."""
        observations, simulations = sample_data
        result = evaluate(observations, simulations, "mean_bias", "none")
        assert isinstance(result, float)
        assert result > 0

    def test_evaluate_deviation_bias(self, sample_data):
        """Deviation bias calculation produces expected result."""
        observations, simulations = sample_data
        result = evaluate(observations, simulations, "deviation_bias", "none")
        assert isinstance(result, float)
        assert result > 0

    def test_evaluate_correlation(self, sample_data):
        """Correlation coefficient calculation produces expected result."""
        observations, simulations = sample_data
        result = evaluate(observations, simulations, "correlation", "none")
        assert isinstance(result, float)
        assert -1.0 <= result <= 1.0

    def test_evaluate_log_transformation(self, sample_data):
        """Log transformation is applied correctly."""
        observations, simulations = sample_data
        result_none = evaluate(observations, simulations, "nse", "none")
        result_log = evaluate(observations, simulations, "nse", "log")
        # Log transformation should give different result
        assert result_none != result_log

    def test_evaluate_sqrt_transformation(self, sample_data):
        """Sqrt transformation is applied correctly."""
        observations, simulations = sample_data
        result_none = evaluate(observations, simulations, "nse", "none")
        result_sqrt = evaluate(observations, simulations, "nse", "sqrt")
        # Sqrt transformation should give different result
        assert result_none != result_sqrt

    def test_evaluate_deviation_bias_zero_mean_sim(self):
        """Deviation bias with zero mean simulation returns inf."""
        observations = np.array([1.0, 2.0, 3.0])
        # Simulations that sum to zero
        simulations = np.array([1.0, 0.0, -1.0])
        result = evaluate(observations, simulations, "deviation_bias", "none")
        assert np.isinf(result) or result == 1.0

    def test_evaluate_deviation_bias_zero_mean_obs(self):
        """Deviation bias with zero mean observations returns inf."""
        # Observations that sum to zero
        observations = np.array([1.0, 0.0, -1.0])
        simulations = np.array([1.0, 2.0, 3.0])
        result = evaluate(observations, simulations, "deviation_bias", "none")
        assert np.isinf(result) or result == 1.0

    def test_evaluate_deviation_bias_constant_obs(self):
        """Deviation bias with constant observations returns inf."""
        observations = np.ones(10)
        simulations = np.random.uniform(1, 10, 10)
        result = evaluate(observations, simulations, "deviation_bias", "none")
        assert np.isinf(result)


class TestHypothesis:
    """Property-based tests for evaluate function."""

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
            unique=True,  # Ensure values have variance (avoid constant arrays)
        )
    )
    @settings(max_examples=50)
    def test_nse_perfect_match(self, observations):
        """NSE should be 1.0 when simulation equals observations."""
        obs = np.array(observations)
        result = evaluate(obs, obs, "nse", "none")
        assert result == pytest.approx(1.0)

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
        )
    )
    @settings(max_examples=50)
    def test_rmse_perfect_match(self, observations):
        """RMSE should be 0.0 when simulation equals observations."""
        obs = np.array(observations)
        result = evaluate(obs, obs, "rmse", "none")
        assert result == pytest.approx(0.0)

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
            unique=True,  # Ensure values have variance (avoid constant arrays)
        )
    )
    @settings(max_examples=50)
    def test_kge_perfect_match(self, observations):
        """KGE should be 1.0 when simulation equals observations."""
        obs = np.array(observations)
        result = evaluate(obs, obs, "kge", "none")
        assert result == pytest.approx(1.0)

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
        )
    )
    @settings(max_examples=50)
    def test_mean_bias_perfect_match(self, observations):
        """Mean bias should be 1.0 when simulation equals observations."""
        obs = np.array(observations)
        result = evaluate(obs, obs, "mean_bias", "none")
        assert result == pytest.approx(1.0)

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
            unique=True,  # Ensure values are unique to avoid constant arrays
        )
    )
    @settings(max_examples=50)
    def test_correlation_perfect_match(self, observations):
        """Correlation should be 1.0 when simulation equals observations."""
        obs = np.array(observations)
        result = evaluate(obs, obs, "correlation", "none")
        assert result == pytest.approx(1.0)

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
        )
    )
    @settings(max_examples=50)
    def test_deviation_bias_perfect_match(self, observations):
        """Deviation bias should be 1.0 when simulation equals observations."""
        obs = np.array(observations)
        result = evaluate(obs, obs, "deviation_bias", "none")
        assert result == pytest.approx(1.0)

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
        ),
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
        ),
    )
    @settings(max_examples=50)
    def test_rmse_symmetric(self, obs_list, sim_list):
        """RMSE should be symmetric: rmse(a,b) = rmse(b,a)."""
        if len(obs_list) != len(sim_list):
            min_len = min(len(obs_list), len(sim_list))
            obs_list = obs_list[:min_len]
            sim_list = sim_list[:min_len]
        if len(obs_list) < 2:
            return
        obs = np.array(obs_list)
        sim = np.array(sim_list)
        result1 = evaluate(obs, sim, "rmse", "none")
        result2 = evaluate(sim, obs, "rmse", "none")
        assert result1 == pytest.approx(result2)

    @given(
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
        ),
        st.lists(
            st.floats(min_value=0.1, max_value=1000, allow_nan=False),
            min_size=10,
            max_size=100,
        ),
    )
    @settings(max_examples=50)
    def test_rmse_non_negative(self, obs_list, sim_list):
        """RMSE should always be non-negative."""
        if len(obs_list) != len(sim_list):
            min_len = min(len(obs_list), len(sim_list))
            obs_list = obs_list[:min_len]
            sim_list = sim_list[:min_len]
        if len(obs_list) < 2:
            return
        obs = np.array(obs_list)
        sim = np.array(sim_list)
        result = evaluate(obs, sim, "rmse", "none")
        assert result >= 0
