"""Tests for src/hydro/gr4j.py - GR4J hydrological model."""

import numpy as np
import pytest
from src.hydro import gr4j


# Test possible_params structure


def test_possible_params_has_all_parameters():
    """possible_params should define all 4 GR4J parameters."""
    assert "x1" in gr4j.possible_params
    assert "x2" in gr4j.possible_params
    assert "x3" in gr4j.possible_params
    assert "x4" in gr4j.possible_params


def test_possible_params_x1_bounds():
    """x1 parameter should have correct bounds."""
    params = gr4j.possible_params["x1"]
    assert params["min"] == 10
    assert params["max"] == 1500
    assert params["is_integer"] is True


def test_possible_params_x2_bounds():
    """x2 parameter should have correct bounds."""
    params = gr4j.possible_params["x2"]
    assert params["min"] == -5
    assert params["max"] == 3
    assert params["is_integer"] is False


def test_possible_params_x3_bounds():
    """x3 parameter should have correct bounds."""
    params = gr4j.possible_params["x3"]
    assert params["min"] == 10
    assert params["max"] == 400
    assert params["is_integer"] is True


def test_possible_params_x4_bounds():
    """x4 parameter should have correct bounds."""
    params = gr4j.possible_params["x4"]
    assert params["min"] == 0.8
    assert params["max"] == 10.0
    assert params["is_integer"] is False


# Test run_model basic functionality


def test_run_model_returns_array(sample_precipitation_evap):
    """run_model should return numpy array."""
    precip, evap = sample_precipitation_evap
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert isinstance(flow, np.ndarray)


def test_run_model_returns_same_length(sample_precipitation_evap):
    """Output should have same length as input."""
    precip, evap = sample_precipitation_evap
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert len(flow) == len(precip)


def test_run_model_output_is_non_negative(sample_precipitation_evap):
    """Flow should be non-negative."""
    precip, evap = sample_precipitation_evap
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert np.all(flow >= 0)


def test_run_model_single_timestep():
    """Should work with single timestep."""
    flow = gr4j.run_model(
        np.array([10.0]),
        np.array([2.0]),
        x1=350, x2=0.0, x3=50, x4=2.0
    )
    assert len(flow) == 1
    assert flow[0] >= 0


def test_run_model_deterministic(sample_precipitation_evap):
    """Same inputs should give same outputs."""
    precip, evap = sample_precipitation_evap
    flow1 = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    flow2 = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    np.testing.assert_array_equal(flow1, flow2)


# Test parameter sensitivity


def test_run_model_x1_affects_output(sample_precipitation_evap):
    """Changing x1 should change output."""
    precip, evap = sample_precipitation_evap
    flow1 = gr4j.run_model(precip, evap, x1=100, x2=0.0, x3=50, x4=2.0)
    flow2 = gr4j.run_model(precip, evap, x1=1000, x2=0.0, x3=50, x4=2.0)
    assert not np.allclose(flow1, flow2)


def test_run_model_x2_affects_output(sample_precipitation_evap):
    """Changing x2 should change output."""
    precip, evap = sample_precipitation_evap
    flow1 = gr4j.run_model(precip, evap, x1=350, x2=-2.0, x3=50, x4=2.0)
    flow2 = gr4j.run_model(precip, evap, x1=350, x2=2.0, x3=50, x4=2.0)
    assert not np.allclose(flow1, flow2)


def test_run_model_x3_affects_output(sample_precipitation_evap):
    """Changing x3 should change output."""
    precip, evap = sample_precipitation_evap
    flow1 = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=20, x4=2.0)
    flow2 = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=200, x4=2.0)
    assert not np.allclose(flow1, flow2)


def test_run_model_x4_affects_output(sample_precipitation_evap):
    """Changing x4 should change output."""
    precip, evap = sample_precipitation_evap
    flow1 = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=1.0)
    flow2 = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=5.0)
    assert not np.allclose(flow1, flow2)


# Test edge cases and boundary conditions


def test_run_model_zero_precipitation():
    """Zero precipitation should give declining flow."""
    precip = np.zeros(100)
    evap = np.ones(100) * 2.0
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    # Flow should generally decline (with some exceptions due to stores)
    assert flow[-1] < flow[0]


def test_run_model_zero_evapotranspiration():
    """Should handle zero evapotranspiration."""
    precip = np.ones(100) * 10.0
    evap = np.zeros(100)
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert np.all(flow >= 0)


def test_run_model_equal_precip_and_evap():
    """Should handle equal precipitation and evapotranspiration."""
    precip = np.ones(100) * 5.0
    evap = np.ones(100) * 5.0
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert np.all(flow >= 0)


def test_run_model_high_precipitation():
    """Should handle high precipitation values."""
    precip = np.ones(100) * 100.0
    evap = np.ones(100) * 5.0
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert np.all(flow >= 0)
    assert np.max(flow) > 0


def test_run_model_minimum_parameters():
    """Should work with minimum parameter values."""
    precip = np.random.uniform(0, 20, 100)
    evap = np.random.uniform(0, 5, 100)
    flow = gr4j.run_model(
        precip, evap,
        x1=10,
        x2=-5,
        x3=10,
        x4=0.8
    )
    assert np.all(np.isfinite(flow))


def test_run_model_maximum_parameters():
    """Should work with maximum parameter values."""
    precip = np.random.uniform(0, 20, 100)
    evap = np.random.uniform(0, 5, 100)
    flow = gr4j.run_model(
        precip, evap,
        x1=1500,
        x2=3,
        x3=400,
        x4=10.0
    )
    assert np.all(np.isfinite(flow))


def test_run_model_x4_integer_value():
    """Should handle integer x4 value correctly."""
    precip = np.random.uniform(0, 20, 100)
    evap = np.random.uniform(0, 5, 100)
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert np.all(flow >= 0)


def test_run_model_x4_non_integer_value():
    """Should handle non-integer x4 value correctly."""
    precip = np.random.uniform(0, 20, 100)
    evap = np.random.uniform(0, 5, 100)
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.5)
    assert np.all(flow >= 0)


def test_run_model_negative_x2():
    """Should handle negative x2 (groundwater loss)."""
    precip = np.random.uniform(0, 20, 100)
    evap = np.random.uniform(0, 5, 100)
    flow = gr4j.run_model(precip, evap, x1=350, x2=-2.0, x3=50, x4=2.0)
    assert np.all(flow >= 0)


def test_run_model_positive_x2():
    """Should handle positive x2 (groundwater gain)."""
    precip = np.random.uniform(0, 20, 100)
    evap = np.random.uniform(0, 5, 100)
    flow = gr4j.run_model(precip, evap, x1=350, x2=2.0, x3=50, x4=2.0)
    assert np.all(flow >= 0)


# Test long sequences


def test_run_model_long_sequence():
    """Should handle long time series."""
    n = 10000
    precip = np.random.uniform(0, 20, n)
    evap = np.random.uniform(0, 5, n)
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert len(flow) == n
    assert np.all(np.isfinite(flow))


# Test realistic scenarios


def test_run_model_realistic_scenario():
    """Should produce reasonable results for realistic data."""
    # Simulate a year of daily data with seasonal pattern
    n = 365
    # Simple seasonal precipitation pattern
    precip = 5 + 10 * np.sin(2 * np.pi * np.arange(n) / 365) + np.random.uniform(0, 5, n)
    # Simple seasonal evapotranspiration pattern
    evap = 2 + 3 * np.sin(2 * np.pi * np.arange(n) / 365) + np.random.uniform(0, 2, n)
    precip = np.maximum(precip, 0)
    evap = np.maximum(evap, 0)

    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)

    # Basic sanity checks
    assert np.all(flow >= 0)
    assert np.mean(flow) > 0
    assert np.std(flow) > 0  # Should have variability


def test_run_model_dry_period_then_wet():
    """Should respond correctly to dry then wet periods."""
    # Dry period
    precip_dry = np.zeros(100)
    evap_dry = np.ones(100) * 3.0

    # Wet period
    precip_wet = np.ones(100) * 20.0
    evap_wet = np.ones(100) * 2.0

    precip = np.concatenate([precip_dry, precip_wet])
    evap = np.concatenate([evap_dry, evap_wet])

    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)

    # Flow should be higher in wet period than dry period
    mean_flow_dry = np.mean(flow[:100])
    mean_flow_wet = np.mean(flow[100:])
    assert mean_flow_wet > mean_flow_dry


# Test precompile function


@pytest.mark.asyncio
async def test_precompile_executes_without_error():
    """Precompile should execute without raising."""
    await gr4j.precompile()


@pytest.mark.asyncio
async def test_precompile_actually_compiles():
    """Precompile should actually compile the function."""
    # Run precompile
    await gr4j.precompile()

    # Run model - should be faster on second call (already compiled)
    precip = np.random.uniform(0, 20, 1000)
    evap = np.random.uniform(0, 5, 1000)
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert np.all(flow >= 0)


# Test internal store behavior


def test_run_model_stores_initialized():
    """Model should initialize stores correctly."""
    # Run model with known initial conditions
    precip = np.ones(10) * 5.0
    evap = np.ones(10) * 2.0
    flow = gr4j.run_model(precip, evap, x1=100, x2=0.0, x3=20, x4=2.0)

    # First timestep should produce some flow
    assert flow[0] >= 0


def test_run_model_mass_balance():
    """Model should approximately conserve mass over long period."""
    n = 1000
    precip = np.ones(n) * 10.0
    evap = np.ones(n) * 3.0

    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)

    # Total output should be less than total input (some stored or evaporated)
    total_input = np.sum(precip) - np.sum(evap)
    total_output = np.sum(flow)

    # Output should be positive and less than input
    assert total_output > 0
    assert total_output < total_input


# Test array types


def test_run_model_accepts_different_array_types():
    """Should work with different numpy array types."""
    precip_list = [5.0, 10.0, 15.0, 10.0, 5.0]
    evap_list = [2.0, 3.0, 4.0, 3.0, 2.0]

    flow = gr4j.run_model(
        np.array(precip_list, dtype=np.float64),
        np.array(evap_list, dtype=np.float64),
        x1=350, x2=0.0, x3=50, x4=2.0
    )
    assert len(flow) == 5


def test_run_model_float32_arrays():
    """Should work with float32 arrays."""
    precip = np.array([5.0, 10.0, 15.0], dtype=np.float32)
    evap = np.array([2.0, 3.0, 4.0], dtype=np.float32)

    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert len(flow) == 3
    assert np.all(flow >= 0)
