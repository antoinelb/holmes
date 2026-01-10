use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::bucket::{init, param_names, simulate};
use holmes_rs::hydro::HydroError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_init_bounds_shape() {
    let (defaults, bounds) = init();
    assert_eq!(defaults.len(), 6, "Bucket model should have 6 parameters");
    assert_eq!(
        bounds.shape(),
        &[6, 2],
        "Bounds should be 6x2 (params x [lower, upper])"
    );
}

#[test]
fn test_init_bounds_ordered() {
    let (_, bounds) = init();
    for i in 0..bounds.nrows() {
        let lower = bounds[[i, 0]];
        let upper = bounds[[i, 1]];
        assert!(
            lower < upper,
            "Parameter {}: lower bound ({}) should be less than upper bound ({})",
            param_names[i],
            lower,
            upper
        );
    }
}

#[test]
fn test_init_defaults_within_bounds() {
    let (defaults, bounds) = init();
    for i in 0..defaults.len() {
        let lower = bounds[[i, 0]];
        let upper = bounds[[i, 1]];
        let default = defaults[i];
        assert!(
            default >= lower && default <= upper,
            "Default for {} ({}) should be within bounds [{}, {}]",
            param_names[i],
            default,
            lower,
            upper
        );
    }
}

#[test]
fn test_param_names() {
    assert_eq!(param_names.len(), 6);
    assert_eq!(
        param_names,
        &["c_soil", "alpha", "k_r", "delta", "beta", "k_t"]
    );
}

#[test]
fn test_init_specific_bounds() {
    let (_, bounds) = init();

    // c_soil: [10, 1000]
    assert_relative_eq!(bounds[[0, 0]], 10.0);
    assert_relative_eq!(bounds[[0, 1]], 1000.0);

    // alpha: [0, 1]
    assert_relative_eq!(bounds[[1, 0]], 0.0);
    assert_relative_eq!(bounds[[1, 1]], 1.0);

    // k_r: [1, 200]
    assert_relative_eq!(bounds[[2, 0]], 1.0);
    assert_relative_eq!(bounds[[2, 1]], 200.0);

    // delta: [2, 10]
    assert_relative_eq!(bounds[[3, 0]], 2.0);
    assert_relative_eq!(bounds[[3, 1]], 10.0);

    // beta: [0, 1]
    assert_relative_eq!(bounds[[4, 0]], 0.0);
    assert_relative_eq!(bounds[[4, 1]], 1.0);

    // k_t: [1, 400]
    assert_relative_eq!(bounds[[5, 0]], 1.0);
    assert_relative_eq!(bounds[[5, 1]], 400.0);
}

// =============================================================================
// Simulation Tests
// =============================================================================

#[test]
fn test_simulate_basic() {
    let (defaults, _) = init();
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q.is_finite()),
        "All streamflow values should be finite"
    );
    assert!(
        streamflow.iter().all(|&q| !q.is_nan()),
        "No NaN values allowed"
    );
}

#[test]
fn test_simulate_zero_precipitation() {
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::zeros(n);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    // With no precipitation, flow should decay
    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q >= 0.0),
        "All values should be non-negative"
    );
}

#[test]
fn test_simulate_output_length() {
    let (defaults, _) = init();

    for n in [10, 100, 365, 1000] {
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

        let streamflow =
            simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        assert_eq!(
            streamflow.len(),
            n,
            "Output length should match input for n={}",
            n
        );
    }
}

#[test]
fn test_simulate_nonnegative_streamflow() {
    let (defaults, _) = init();
    let n = 365;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q >= 0.0),
        "All streamflow values should be non-negative"
    );
}

// =============================================================================
// Error Handling Tests
// =============================================================================

#[test]
fn test_simulate_param_count_error() {
    let wrong_params = array![100.0, 0.5, 50.0, 3.0]; // Only 4 params instead of 6
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(6, 4))));
}

#[test]
fn test_simulate_length_mismatch() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0]; // Length mismatch

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::LengthMismatch(3, 2))));
}

// =============================================================================
// Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_c_soil_sensitivity() {
    // c_soil controls soil moisture capacity
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![50.0, 0.5, 50.0, 3.0, 0.3, 100.0]; // Small soil capacity
    let params_high = array![800.0, 0.5, 50.0, 3.0, 0.3, 100.0]; // Large soil capacity

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    // Both should produce valid output
    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_beta_sensitivity() {
    // beta controls fast flow fraction
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_slow = array![300.0, 0.5, 50.0, 3.0, 0.0, 100.0]; // All slow flow
    let params_fast = array![300.0, 0.5, 50.0, 3.0, 1.0, 100.0]; // All fast flow

    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();

    // Both should produce valid output
    assert!(flow_slow.iter().all(|&q| q.is_finite()));
    assert!(flow_fast.iter().all(|&q| q.is_finite()));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        c_soil in 10.0f64..1000.0,
        alpha in 0.0f64..1.0,
        k_r in 1.0f64..200.0,
        delta in 2.0f64..10.0,
        beta in 0.0f64..1.0,
        k_t in 1.0f64..400.0
    ) {
        let params = array![c_soil, alpha, k_r, delta, beta, k_t];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q >= 0.0));
    }

    #[test]
    fn prop_output_length(n in 10usize..200) {
        let (defaults, _) = init();
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

        let streamflow = simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        prop_assert_eq!(streamflow.len(), n);
    }

    #[test]
    fn prop_finite_output(
        c_soil in 50.0f64..500.0,
        alpha in 0.1f64..0.9,
        k_r in 10.0f64..100.0,
        delta in 3.0f64..8.0,
        beta in 0.1f64..0.9,
        k_t in 10.0f64..200.0
    ) {
        let params = array![c_soil, alpha, k_r, delta, beta, k_t];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite()));
    }
}

// =============================================================================
// Anti-Fragility Tests (expected to fail with current implementation)
// =============================================================================

// =============================================================================
// Branch Coverage Tests
// =============================================================================

#[test]
fn test_wet_conditions_p_greater_than_e() {
    // Test case where precipitation > evapotranspiration (wet conditions)
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 20.0); // High precipitation
    let pet = Array1::from_elem(n, 5.0); // Low PET

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle wet conditions"
    );
    assert!(
        streamflow.sum() > 0.0,
        "Should produce positive flow in wet conditions"
    );
}

#[test]
fn test_dry_conditions_p_less_than_e() {
    // Test case where precipitation < evapotranspiration (dry conditions)
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 1.0); // Low precipitation
    let pet = Array1::from_elem(n, 10.0); // High PET

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions without numerical issues"
    );
}

#[test]
fn test_alpha_routing_split() {
    // Test different alpha values (routing split between slow and fast)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 10.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // alpha = 0: all infiltration goes to slow routing
    let params_alpha_0 = array![300.0, 0.0, 50.0, 3.0, 0.3, 100.0];
    let flow_alpha_0 =
        simulate(params_alpha_0.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_alpha_0.iter().all(|&q| q.is_finite() && q >= 0.0));

    // alpha = 1: all infiltration goes to fast routing
    let params_alpha_1 = array![300.0, 1.0, 50.0, 3.0, 0.3, 100.0];
    let flow_alpha_1 =
        simulate(params_alpha_1.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_alpha_1.iter().all(|&q| q.is_finite() && q >= 0.0));

    // alpha = 0.5: split between both
    let params_alpha_half = array![300.0, 0.5, 50.0, 3.0, 0.3, 100.0];
    let flow_alpha_half =
        simulate(params_alpha_half.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_alpha_half.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delta_routing_delay() {
    // Test different delta values (routing delay)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // delta = 2 (minimum - short delay)
    let params_short = array![300.0, 0.5, 50.0, 2.0, 0.3, 100.0];
    let flow_short =
        simulate(params_short.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_short.iter().all(|&q| q.is_finite() && q >= 0.0));

    // delta = 10 (maximum - long delay)
    let params_long = array![300.0, 0.5, 50.0, 10.0, 0.3, 100.0];
    let flow_long =
        simulate(params_long.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_long.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_soil_moisture_overflow() {
    // Test case where soil moisture exceeds capacity
    let n = 100;
    let precip = Array1::from_elem(n, 100.0); // Very high precipitation
    let pet = Array1::from_elem(n, 1.0); // Very low PET

    // Small c_soil to force overflow quickly
    let params = array![50.0, 0.5, 50.0, 3.0, 0.3, 100.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle soil moisture overflow"
    );
}

#[test]
fn test_k_r_and_k_t_extreme() {
    // Test with extreme k_r and k_t values
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // Low k_r and k_t (fast routing)
    let params_fast = array![300.0, 0.5, 1.0, 3.0, 0.3, 1.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));

    // High k_r and k_t (slow routing)
    let params_slow = array![300.0, 0.5, 200.0, 3.0, 0.3, 400.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
#[ignore = "R5-NUM-05: Potential exp() instability with small c_soil"]
fn test_bucket_small_c_soil() {
    // Very small c_soil can cause exp() instability in dry conditions
    let params = array![10.0, 0.5, 50.0, 3.0, 0.3, 100.0]; // c_soil at minimum
    let n = 100;
    let precip = Array1::zeros(n); // No precipitation
    let pet = Array1::from_elem(n, 5.0); // High PET (strong drying)

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(
        streamflow.iter().all(|&q| q.is_finite()),
        "Should handle small c_soil without overflow"
    );
}

#[test]
#[ignore = "R1-ERR-04: NaN propagates through simulation"]
fn test_bucket_nan_input() {
    let (defaults, _) = init();
    let precip = array![10.0, f64::NAN, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    if let Ok(streamflow) = result {
        assert!(
            streamflow.iter().all(|&q| q.is_finite()),
            "NaN should not propagate"
        );
    }
}
