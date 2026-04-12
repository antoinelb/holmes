use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::martine::{
    init, param_descriptions, param_names, simulate,
};
use holmes_rs::hydro::HydroError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_init_bounds_shape() {
    let (defaults, bounds) = init();
    assert_eq!(defaults.len(), 7, "MARTINE model should have 7 parameters");
    assert_eq!(
        bounds.shape(),
        &[7, 2],
        "Bounds should be 7x2 (params x [lower, upper])"
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
    assert_eq!(param_names.len(), 7);
    assert_eq!(
        param_names,
        &["x1", "x2", "x3", "x4", "x5", "x6", "x7"]
    );
}

#[test]
fn test_param_descriptions() {
    assert_eq!(param_descriptions.len(), param_names.len());
    for desc in param_descriptions {
        assert!(!desc.is_empty(), "Description should not be empty");
    }
}

#[test]
fn test_init_specific_bounds() {
    let (_, bounds) = init();

    // x1 (surface reservoir capacity): [1, 2000]
    assert_relative_eq!(bounds[[0, 0]], 1.0);
    assert_relative_eq!(bounds[[0, 1]], 2000.0);

    // x2 (intermediate reservoir capacity): [1, 2000]
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 2000.0);

    // x3 (quadratic routing reservoir capacity): [0.01, 1000]
    assert_relative_eq!(bounds[[2, 0]], 0.01);
    assert_relative_eq!(bounds[[2, 1]], 1000.0);

    // x4 (groundwater emptying constant): [1, 500]
    assert_relative_eq!(bounds[[3, 0]], 1.0);
    assert_relative_eq!(bounds[[3, 1]], 500.0);

    // x5 (distribution coefficient): [0.01, 0.99]
    assert_relative_eq!(bounds[[4, 0]], 0.01);
    assert_relative_eq!(bounds[[4, 1]], 0.99);

    // x6 (delay): [0.5, 5.0]
    assert_relative_eq!(bounds[[5, 0]], 0.5);
    assert_relative_eq!(bounds[[5, 1]], 5.0);

    // x7 (intermediate reservoir emptying constant): [1, 500]
    assert_relative_eq!(bounds[[6, 0]], 1.0);
    assert_relative_eq!(bounds[[6, 1]], 500.0);
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

    // With no precipitation, flow should decay from initial reservoir states
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
    let wrong_params = array![100.0, 0.5, 50.0, 3.0]; // Only 4 params instead of 7
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(7, 4))));
}

#[test]
fn test_simulate_length_mismatch() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0]; // Length mismatch

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::LengthMismatch(3, 2))));
}

#[test]
fn test_martine_nan_input() {
    let (defaults, _) = init();
    let precip = array![10.0, f64::NAN, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NonFiniteInput { .. })),
        "Should reject NaN in precipitation"
    );
}

#[test]
fn test_martine_negative_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, -5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NegativeInput { .. })),
        "Should reject negative precipitation"
    );
}

#[test]
fn test_martine_nan_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, f64::NAN, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NonFiniteInput { .. })),
        "Should reject NaN in PET"
    );
}

#[test]
fn test_martine_negative_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, -1.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NegativeInput { .. })),
        "Should reject negative PET"
    );
}

#[test]
fn test_martine_empty_arrays() {
    let (defaults, _) = init();
    let precip: Array1<f64> = array![];
    let pet: Array1<f64> = array![];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::EmptyInput { .. })),
        "Should reject empty input arrays"
    );
}

#[test]
fn test_martine_params_outside_bounds() {
    // x1 way above upper bound (2000)
    let params = array![5000.0, 1000.0, 500.0, 250.0, 0.5, 2.5, 250.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject out-of-bounds parameters"
    );
}

// =============================================================================
// Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_x1_sensitivity() {
    // x1 controls surface reservoir capacity: Pr = max(0, S - X1)
    // Higher x1 means more storage before overflow → less runoff
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small = array![10.0, 1000.0, 500.0, 250.0, 0.5, 2.5, 250.0];
    let params_large = array![1900.0, 1000.0, 500.0, 250.0, 0.5, 2.5, 250.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x5_sensitivity() {
    // x5 is distribution coefficient: splits Pr between routing (x5) and intermediate (1-x5)
    // Higher x5 means more direct routing, less groundwater
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![1000.0, 1000.0, 500.0, 250.0, 0.1, 2.5, 250.0];
    let params_high = array![1000.0, 1000.0, 500.0, 250.0, 0.9, 2.5, 250.0];

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x4_groundwater_recession() {
    // x4 controls groundwater emptying: Ql = L / x4
    // Higher x4 means slower groundwater emptying
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![1000.0, 1000.0, 500.0, 1.0, 0.5, 2.5, 250.0];
    let params_slow = array![1000.0, 1000.0, 500.0, 500.0, 0.5, 2.5, 250.0];

    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_fast.iter().all(|&q| q.is_finite()));
    assert!(flow_slow.iter().all(|&q| q.is_finite()));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 1.0f64..2000.0,
        x2 in 1.0f64..2000.0,
        x3 in 0.01f64..1000.0,
        x4 in 1.0f64..500.0,
        x5 in 0.01f64..0.99,
        x6 in 0.5f64..5.0,
        x7 in 1.0f64..500.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7];
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
        x1 in 50.0f64..1000.0,
        x2 in 50.0f64..1000.0,
        x3 in 50.0f64..500.0,
        x4 in 10.0f64..250.0,
        x5 in 0.1f64..0.9,
        x6 in 1.0f64..4.0,
        x7 in 10.0f64..250.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite()));
    }
}

// =============================================================================
// Branch Coverage Tests
// =============================================================================

#[test]
fn test_wet_conditions_p_greater_than_e() {
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
fn test_overflow_occurs() {
    // Small X1 with high precipitation forces S > X1, triggering overflow
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![10.0, 1000.0, 500.0, 250.0, 0.5, 2.5, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0, "Overflow should produce runoff");
}

#[test]
fn test_no_overflow() {
    // Large X1 with low precipitation: S stays below X1, no overflow
    let n = 50;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![2000.0, 1000.0, 500.0, 250.0, 0.5, 2.5, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_intermediate_overflow() {
    // Small X2 with heavy rainfall: T exceeds X2, triggering Qt2 overflow
    let n = 100;
    let precip = Array1::from_elem(n, 30.0);
    let pet = Array1::from_elem(n, 2.0);

    // Small x1 → lots of overflow; small x2 → intermediate overflows; low x5 → more to T
    let params = array![5.0, 10.0, 500.0, 250.0, 0.1, 2.5, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(
        streamflow.sum() > 0.0,
        "Intermediate overflow should produce flow"
    );
}

#[test]
fn test_residual_et_dries_intermediate() {
    // Heavy ET, no precipitation — residual ET should dry out T via max(0, T-Et)
    let n = 200;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 20.0);

    let (defaults, _) = init();
    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle intermediate drying without numerical issues"
    );
}

#[test]
fn test_delay_parameter_short() {
    // x6 at minimum (0.5) — short delay
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1000.0, 1000.0, 500.0, 250.0, 0.5, 0.5, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    // x6 at maximum (5.0) — long delay
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1000.0, 1000.0, 500.0, 250.0, 0.5, 5.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_integer() {
    // x6 = 2.0 (exact integer) — tests edge case in delay vector construction
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1000.0, 1000.0, 500.0, 250.0, 0.5, 2.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_quadratic_routing_high_inflow() {
    // Very high precipitation to stress the quadratic emptying Qr = R² / (R + X3)
    let n = 100;
    let precip = Array1::from_elem(n, 100.0);
    let pet = Array1::from_elem(n, 1.0);

    // Small X1 so almost all rain overflows, high X5 sends most to routing
    let params = array![1.0, 1000.0, 500.0, 250.0, 0.9, 2.5, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle high routing reservoir inflow"
    );
}

#[test]
fn test_x3_routing_capacity() {
    // x3 controls quadratic routing: Qr = R² / (R + X3)
    // Small x3 → more aggressive emptying, large x3 → slower
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small = array![1000.0, 1000.0, 0.01, 250.0, 0.5, 2.5, 250.0];
    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_small.iter().all(|&q| q.is_finite() && q >= 0.0));

    let params_large = array![1000.0, 1000.0, 1000.0, 250.0, 0.5, 2.5, 250.0];
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_large.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x7_intermediate_emptying() {
    // x7 controls intermediate emptying: Qt1 = T / x7
    // Small x7 → fast intermediate emptying, large x7 → slow
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![1000.0, 1000.0, 500.0, 250.0, 0.5, 2.5, 1.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));

    let params_slow = array![1000.0, 1000.0, 500.0, 250.0, 0.5, 2.5, 500.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_groundwater_extreme_recession() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // x4 = 1 (very fast groundwater emptying)
    let params_fast = array![1000.0, 1000.0, 500.0, 1.0, 0.5, 2.5, 250.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x4 = 500 (very slow groundwater emptying)
    let params_slow = array![1000.0, 1000.0, 500.0, 500.0, 0.5, 2.5, 250.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}
