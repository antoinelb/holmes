"""
Tests for metrics module PyO3 bindings.

These tests verify that calculate_rmse, calculate_nse, and calculate_kge
work correctly when called from Python.
"""

import numpy as np
import pytest
from numpy.testing import assert_almost_equal

from holmes_rs import metrics


class TestCalculateRmse:
    """Tests for calculate_rmse function."""

    def test_perfect_prediction(self):
        """RMSE should be 0 for perfect predictions."""
        obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sim = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        rmse = metrics.calculate_rmse(obs, sim)

        assert_almost_equal(rmse, 0.0)

    def test_known_value(self):
        """Test RMSE calculation with known values."""
        obs = np.array([1.0, 2.0, 3.0])
        sim = np.array([2.0, 3.0, 4.0])  # All off by 1

        rmse = metrics.calculate_rmse(obs, sim)

        assert_almost_equal(rmse, 1.0)

    def test_nonnegative(self):
        """RMSE should always be non-negative."""
        np.random.seed(42)
        obs = np.random.rand(100)
        sim = np.random.rand(100)

        rmse = metrics.calculate_rmse(obs, sim)

        assert rmse >= 0.0

    def test_symmetric(self):
        """RMSE should be symmetric: RMSE(a, b) == RMSE(b, a)."""
        obs = np.array([1.0, 2.0, 3.0, 4.0])
        sim = np.array([1.5, 2.5, 2.5, 4.5])

        rmse1 = metrics.calculate_rmse(obs, sim)
        rmse2 = metrics.calculate_rmse(sim, obs)

        assert_almost_equal(rmse1, rmse2)

    def test_length_mismatch_raises(self):
        """Should raise error for mismatched array lengths."""
        obs = np.array([1.0, 2.0, 3.0])
        sim = np.array([1.0, 2.0])

        with pytest.raises(ValueError, match="same length"):
            metrics.calculate_rmse(obs, sim)


class TestCalculateNse:
    """Tests for calculate_nse function."""

    def test_perfect_prediction(self):
        """NSE should be 1.0 for perfect predictions."""
        obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sim = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        nse = metrics.calculate_nse(obs, sim)

        assert_almost_equal(nse, 1.0)

    def test_mean_prediction(self):
        """NSE should be 0.0 when predicting mean of observations."""
        obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        mean_obs = np.mean(obs)
        sim = np.full_like(obs, mean_obs)

        nse = metrics.calculate_nse(obs, sim)

        assert_almost_equal(nse, 0.0)

    def test_upper_bound(self):
        """NSE should not exceed 1.0."""
        np.random.seed(42)
        obs = np.random.rand(100) + 1  # Avoid zeros
        sim = np.random.rand(100) + 1

        nse = metrics.calculate_nse(obs, sim)

        assert nse <= 1.0

    def test_worse_than_mean(self):
        """NSE should be negative when predictions are worse than mean."""
        obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sim = np.array([5.0, 4.0, 3.0, 2.0, 1.0])  # Inverted

        nse = metrics.calculate_nse(obs, sim)

        assert nse < 0.0

    def test_length_mismatch_raises(self):
        """Should raise error for mismatched array lengths."""
        obs = np.array([1.0, 2.0, 3.0])
        sim = np.array([1.0, 2.0])

        with pytest.raises(ValueError, match="same length"):
            metrics.calculate_nse(obs, sim)


class TestCalculateKge:
    """Tests for calculate_kge function."""

    def test_perfect_prediction(self):
        """KGE should be 1.0 for perfect predictions."""
        obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sim = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

        kge = metrics.calculate_kge(obs, sim)

        assert_almost_equal(kge, 1.0)

    def test_upper_bound(self):
        """KGE should not exceed 1.0."""
        np.random.seed(42)
        obs = np.random.rand(100) + 1
        sim = np.random.rand(100) + 1

        kge = metrics.calculate_kge(obs, sim)

        assert kge <= 1.0

    def test_scaled_simulation(self):
        """Test KGE with scaled simulations (bias in mean)."""
        obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        sim = obs * 2.0  # Double the values

        kge = metrics.calculate_kge(obs, sim)

        # KGE should be less than 1 due to bias
        assert kge < 1.0
        assert np.isfinite(kge)

    def test_length_mismatch_raises(self):
        """Should raise error for mismatched array lengths."""
        obs = np.array([1.0, 2.0, 3.0])
        sim = np.array([1.0, 2.0])

        with pytest.raises(ValueError, match="same length"):
            metrics.calculate_kge(obs, sim)


class TestMetricsIntegration:
    """Integration tests for metrics module."""

    def test_module_accessible(self):
        """Metrics module should be accessible from holmes_rs."""
        assert hasattr(metrics, "calculate_rmse")
        assert hasattr(metrics, "calculate_nse")
        assert hasattr(metrics, "calculate_kge")

    def test_all_metrics_finite_output(self):
        """All metrics should produce finite output for valid input."""
        np.random.seed(42)
        obs = np.random.rand(100) + 1
        sim = np.random.rand(100) + 1

        rmse = metrics.calculate_rmse(obs, sim)
        nse = metrics.calculate_nse(obs, sim)
        kge = metrics.calculate_kge(obs, sim)

        assert np.isfinite(rmse)
        assert np.isfinite(nse)
        assert np.isfinite(kge)
