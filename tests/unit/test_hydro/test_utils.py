"""Tests for src/hydro/utils.py - evaluation criteria and utilities."""

import numpy as np
import pytest
from holmes.hydro import utils


# Test RMSE objective function


def test_evaluate_rmse_perfect_match(perfect_match):
    """RMSE should be 0 for perfect match."""
    obs, sim = perfect_match
    rmse = utils.evaluate_simulation(obs, sim, "rmse", "none")
    assert rmse == pytest.approx(0.0)


def test_evaluate_rmse_is_non_negative(poor_match):
    """RMSE should always be non-negative."""
    obs, sim = poor_match
    rmse = utils.evaluate_simulation(obs, sim, "rmse", "none")
    assert rmse >= 0


def test_evaluate_rmse_known_value():
    """RMSE should match expected value for known data."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([1.5, 2.5, 3.5, 4.5, 5.5])
    # Expected RMSE = sqrt(mean((0.5, 0.5, 0.5, 0.5, 0.5)^2)) = 0.5
    rmse = utils.evaluate_simulation(obs, sim, "rmse", "none")
    assert rmse == pytest.approx(0.5)


# Test NSE objective function


def test_evaluate_nse_perfect_match(perfect_match):
    """NSE should be 1 for perfect match."""
    obs, sim = perfect_match
    nse = utils.evaluate_simulation(obs, sim, "nse", "none")
    assert nse == pytest.approx(1.0)


def test_evaluate_nse_range(poor_match):
    """NSE should be <= 1 (can be negative)."""
    obs, sim = poor_match
    nse = utils.evaluate_simulation(obs, sim, "nse", "none")
    assert nse <= 1


def test_evaluate_nse_mean_prediction():
    """NSE should be 0 when simulation equals mean of observations."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.full(5, 3.0)  # Mean of obs
    nse = utils.evaluate_simulation(obs, sim, "nse", "none")
    assert nse == pytest.approx(0.0, abs=1e-10)


def test_evaluate_nse_negative_for_bad_simulation():
    """NSE should be negative for very poor simulation."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([10.0, 10.0, 10.0, 10.0, 10.0])
    nse = utils.evaluate_simulation(obs, sim, "nse", "none")
    assert nse < 0


# Test KGE objective function


def test_evaluate_kge_perfect_match(perfect_match):
    """KGE should be 1 for perfect match."""
    obs, sim = perfect_match
    kge = utils.evaluate_simulation(obs, sim, "kge", "none")
    assert kge == pytest.approx(1.0)


def test_evaluate_kge_range(poor_match):
    """KGE should be <= 1."""
    obs, sim = poor_match
    kge = utils.evaluate_simulation(obs, sim, "kge", "none")
    assert kge <= 1


# Test mean bias


def test_evaluate_mean_bias_perfect_match(perfect_match):
    """Mean bias should be 1 for perfect match."""
    obs, sim = perfect_match
    bias = utils.evaluate_simulation(obs, sim, "mean_bias", "none")
    assert bias == pytest.approx(1.0)


def test_evaluate_mean_bias_overestimation():
    """Mean bias > 1 indicates overestimation."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    bias = utils.evaluate_simulation(obs, sim, "mean_bias", "none")
    assert bias == pytest.approx(2.0)


def test_evaluate_mean_bias_underestimation():
    """Mean bias < 1 indicates underestimation."""
    obs = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    sim = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    bias = utils.evaluate_simulation(obs, sim, "mean_bias", "none")
    assert bias == pytest.approx(0.5)


# Test deviation bias


def test_evaluate_deviation_bias_perfect_match(perfect_match):
    """Deviation bias should be 1 for perfect match."""
    obs, sim = perfect_match
    dev_bias = utils.evaluate_simulation(obs, sim, "deviation_bias", "none")
    assert dev_bias == pytest.approx(1.0)


def test_evaluate_deviation_bias_higher_variance():
    """Deviation bias > 1 indicates higher variability in simulation."""
    obs = np.array([3.0, 3.0, 3.0, 3.0, 3.0])
    sim = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    dev_bias = utils.evaluate_simulation(obs, sim, "deviation_bias", "none")
    assert dev_bias > 1


# Test correlation


def test_evaluate_correlation_perfect_match(perfect_match):
    """Correlation should be 1 for perfect match."""
    obs, sim = perfect_match
    corr = utils.evaluate_simulation(obs, sim, "correlation", "none")
    assert corr == pytest.approx(1.0)


def test_evaluate_correlation_perfect_negative():
    """Correlation should be -1 for perfect negative correlation."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
    corr = utils.evaluate_simulation(obs, sim, "correlation", "none")
    assert corr == pytest.approx(-1.0)


def test_evaluate_correlation_no_correlation():
    """Correlation should be near 0 for uncorrelated data."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([3.0, 1.0, 4.0, 5.0, 2.0])
    corr = utils.evaluate_simulation(obs, sim, "correlation", "none")
    # Not exactly 0, but should be low
    assert -0.5 < corr < 0.5


# Test transformations


def test_evaluate_log_transformation():
    """Log transformation should handle low values."""
    obs = np.array([0.001, 0.01, 0.1, 1.0, 10.0])
    sim = np.array([0.002, 0.02, 0.2, 2.0, 20.0])
    result = utils.evaluate_simulation(obs, sim, "rmse", "log")
    assert isinstance(result, float)
    assert result >= 0


def test_evaluate_log_transformation_prevents_inf():
    """Log transformation should prevent -inf values."""
    obs = np.array([0.0, 0.1, 1.0, 10.0])
    sim = np.array([0.0, 0.2, 2.0, 20.0])
    # Should not raise error or return inf/nan
    result = utils.evaluate_simulation(obs, sim, "rmse", "log")
    assert np.isfinite(result)


def test_evaluate_sqrt_transformation():
    """Sqrt transformation should work correctly."""
    obs = np.array([1.0, 4.0, 9.0, 16.0, 25.0])
    sim = np.array([1.0, 4.0, 9.0, 16.0, 25.0])
    nse = utils.evaluate_simulation(obs, sim, "nse", "sqrt")
    assert nse == pytest.approx(1.0)


def test_evaluate_sqrt_transformation_changes_result():
    """Sqrt transformation should change the result."""
    obs = np.array([1.0, 4.0, 9.0, 16.0, 25.0])
    sim = np.array([1.5, 4.5, 9.5, 16.5, 25.5])

    rmse_none = utils.evaluate_simulation(obs, sim, "rmse", "none")
    rmse_sqrt = utils.evaluate_simulation(obs, sim, "rmse", "sqrt")

    # The two should be different
    assert rmse_none != rmse_sqrt


def test_evaluate_none_transformation():
    """None transformation should not modify data."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([1.0, 2.0, 3.0, 4.0, 5.0])

    # All criteria should give optimal value
    assert utils.evaluate_simulation(
        obs, sim, "rmse", "none"
    ) == pytest.approx(0.0)
    assert utils.evaluate_simulation(obs, sim, "nse", "none") == pytest.approx(
        1.0
    )


# Test combinations of criteria and transformations


@pytest.mark.parametrize(
    "criteria", ["rmse", "nse", "kge", "mean_bias", "correlation"]
)
@pytest.mark.parametrize("transformation", ["none", "log", "sqrt"])
def test_evaluate_all_criteria_with_transformations(criteria, transformation):
    """All criteria should work with all transformations."""
    obs = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    sim = np.array([1.1, 2.1, 3.1, 4.1, 5.1])

    result = utils.evaluate_simulation(obs, sim, criteria, transformation)
    assert isinstance(result, float)
    assert np.isfinite(result)


# Test get_optimal_for_criteria


def test_get_optimal_for_criteria_rmse():
    """RMSE optimal is 0."""
    assert utils.get_optimal_for_criteria("rmse") == 0


def test_get_optimal_for_criteria_nse():
    """NSE optimal is 1."""
    assert utils.get_optimal_for_criteria("nse") == 1


def test_get_optimal_for_criteria_kge():
    """KGE optimal is 1."""
    assert utils.get_optimal_for_criteria("kge") == 1


def test_get_optimal_for_criteria_correlation():
    """Correlation optimal is 1."""
    assert utils.get_optimal_for_criteria("correlation") == 1


def test_get_optimal_for_criteria_mean_bias():
    """Mean bias optimal is 1."""
    assert utils.get_optimal_for_criteria("mean_bias") == 1


def test_get_optimal_for_criteria_deviation_bias():
    """Deviation bias optimal is 1."""
    assert utils.get_optimal_for_criteria("deviation_bias") == 1


# Test edge cases


def test_evaluate_single_value():
    """Should handle single value arrays."""
    obs = np.array([5.0])
    sim = np.array([5.0])

    # RMSE should work
    rmse = utils.evaluate_simulation(obs, sim, "rmse", "none")
    assert rmse == pytest.approx(0.0)


def test_evaluate_large_array():
    """Should handle large arrays efficiently."""
    n = 10000
    obs = np.random.uniform(0, 100, n)
    sim = obs + np.random.normal(0, 1, n)

    # Should complete without error
    rmse = utils.evaluate_simulation(obs, sim, "rmse", "none")
    assert isinstance(rmse, float)
    assert rmse >= 0


def test_evaluate_with_zeros():
    """Should handle arrays with zero values."""
    obs = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    sim = np.array([0.0, 1.1, 2.1, 3.1, 4.1])

    # Should work with log transformation (clips to 10^-5)
    result = utils.evaluate_simulation(obs, sim, "rmse", "log")
    assert np.isfinite(result)


def test_evaluate_with_constant_observation():
    """Should handle constant observation arrays."""
    obs = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
    sim = np.array([4.0, 5.0, 6.0, 5.0, 5.0])

    # NSE calculation has division by sum((obs - mean(obs))^2) which is 0
    # This should still work (will be -inf or similar)
    nse = utils.evaluate_simulation(obs, sim, "nse", "none")
    # NSE is typically -inf when obs is constant
    assert nse <= 0 or np.isinf(nse)


# Test hydrological_models dictionary


def test_hydrological_models_contains_gr4j():
    """hydrological_models should contain GR4J."""
    assert "GR4J" in utils.hydrological_models


def test_hydrological_models_gr4j_has_parameters():
    """GR4J should have parameters defined."""
    assert "parameters" in utils.hydrological_models["GR4J"]
    params = utils.hydrological_models["GR4J"]["parameters"]
    assert isinstance(params, dict)
    assert len(params) > 0


# Test edge cases for deviation_bias


def test_evaluate_deviation_bias_both_means_zero():
    """Deviation bias when both flow and sim have mean of zero."""
    obs = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    sim = np.array([0.0, 0.0, 0.0, 0.0, 0.0])

    # When both means are 0 and equal, should return 1.0
    bias = utils.evaluate_simulation(obs, sim, "deviation_bias", "none")
    assert bias == 1.0
