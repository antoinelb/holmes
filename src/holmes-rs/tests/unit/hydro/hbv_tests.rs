use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::hbv::{init, param_descriptions, param_names, simulate};
use holmes_rs::hydro::HydroError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_init_bounds_shape() {
    let (defaults, bounds) = init();
    assert_eq!(defaults.len(), 9, "HBV model should have 9 parameters");
    assert_eq!(
        bounds.shape(),
        &[9, 2],
        "Bounds should be 9x2 (params x [lower, upper])"
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
            "Parameter {}: lower ({}) should be less than upper ({})",
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
    assert_eq!(param_names.len(), 9);
    assert_eq!(
        param_names,
        &["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"]
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

    // x1 (soil reservoir capacity): [100, 1000]
    assert_relative_eq!(bounds[[0, 0]], 100.0);
    assert_relative_eq!(bounds[[0, 1]], 1000.0);

    // x2 (PET threshold): [1, 1000] — lower tightened from HOOPLA's 0 for safety
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 1000.0);

    // x3 (upper emptying constant of intermediate reservoir): [1, 20]
    assert_relative_eq!(bounds[[2, 0]], 1.0);
    assert_relative_eq!(bounds[[2, 1]], 20.0);

    // x4 (ground reservoir emptying constant): [1, 100]
    assert_relative_eq!(bounds[[3, 0]], 1.0);
    assert_relative_eq!(bounds[[3, 1]], 100.0);

    // x5 (percolation coefficient): [1, 20]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 20.0);

    // x6 (triangular UH time base): [2, 40] — must be >= 2 for UH construction
    assert_relative_eq!(bounds[[5, 0]], 2.0);
    assert_relative_eq!(bounds[[5, 1]], 40.0);

    // x7 (soil nonlinearity exponent): [0, 50]
    assert_relative_eq!(bounds[[6, 0]], 0.0);
    assert_relative_eq!(bounds[[6, 1]], 50.0);

    // x8 (flow threshold of intermediate reservoir): [0, 100]
    assert_relative_eq!(bounds[[7, 0]], 0.0);
    assert_relative_eq!(bounds[[7, 1]], 100.0);

    // x9 (lower emptying constant): [1, 20] — lower tightened from HOOPLA's 0
    // so that x3*x9 >= 1, guaranteeing R stays non-negative
    assert_relative_eq!(bounds[[8, 0]], 1.0);
    assert_relative_eq!(bounds[[8, 1]], 20.0);
}

// =============================================================================
// Simulation Tests
// =============================================================================

#[test]
fn test_simulate_basic() {
    let (defaults, _) = init();
    let n = 365;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q.is_finite()),
        "All streamflow values should be finite"
    );
}

#[test]
fn test_simulate_zero_precipitation() {
    let (defaults, _) = init();
    let n = 200;
    let precip = Array1::zeros(n);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q >= 0.0 && q.is_finite()),
        "All values should be non-negative and finite"
    );
    // With no precip, flow should strictly decay after the initial reservoirs
    // drain — the last value should be <= the first few.
    assert!(streamflow[n - 1] <= streamflow[10]);
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
fn test_simulate_param_count_error_too_few() {
    let wrong_params = array![500.0, 500.0, 10.0, 50.0, 10.0]; // 5 instead of 9
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(9, 5))));
}

#[test]
fn test_simulate_param_count_error_too_many() {
    let wrong_params =
        array![500.0, 500.0, 10.0, 50.0, 10.0, 20.0, 1.0, 50.0, 10.0, 5.0]; // 10
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(9, 10))));
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
fn test_hbv_nan_precipitation() {
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
fn test_hbv_nan_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, f64::NAN, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NonFiniteInput { .. })),
        "Should reject NaN in pet"
    );
}

#[test]
fn test_hbv_infinity_input() {
    let (defaults, _) = init();
    let precip = array![10.0, f64::INFINITY, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NonFiniteInput { .. })));
}

#[test]
fn test_hbv_negative_precipitation() {
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
fn test_hbv_negative_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, -1.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NegativeInput { .. })));
}

#[test]
fn test_hbv_empty_arrays() {
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
fn test_hbv_x1_below_lower_bound() {
    // x1 = 50 is below the [100, 1000] lower bound
    let params = array![50.0, 500.0, 10.0, 50.0, 10.0, 20.0, 1.0, 50.0, 10.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x1", .. })
    ));
}

#[test]
fn test_hbv_x1_above_upper_bound() {
    // x1 = 2000 is above the [100, 1000] upper bound
    let params =
        array![2000.0, 500.0, 10.0, 50.0, 10.0, 20.0, 1.0, 50.0, 10.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x1", .. })
    ));
}

#[test]
fn test_hbv_x2_at_zero_rejected() {
    // HOOPLA allows x2=0 but HOLMES tightened the lower bound to 1.0
    // to avoid division by zero in E*S/x2.
    let params = array![500.0, 0.0, 10.0, 50.0, 10.0, 20.0, 1.0, 50.0, 10.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x2", .. })
    ));
}

#[test]
fn test_hbv_x6_below_two_rejected() {
    // x6 < 2 would make the rising limb empty and break UH normalization
    let params = array![500.0, 500.0, 10.0, 50.0, 10.0, 1.0, 1.0, 50.0, 10.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x6", .. })
    ));
}

#[test]
fn test_hbv_x9_at_zero_rejected() {
    // HOOPLA allows x9=0 but HOLMES tightened to 1.0 so x3*x9 >= 1.
    let params = array![500.0, 500.0, 10.0, 50.0, 10.0, 20.0, 1.0, 50.0, 0.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x9", .. })
    ));
}

#[test]
fn test_hbv_nan_parameter_rejected() {
    let params =
        array![500.0, 500.0, 10.0, f64::NAN, 10.0, 20.0, 1.0, 50.0, 10.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x4", .. })
    ));
}

// =============================================================================
// Branch / Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_wet_conditions_p_greater_than_e() {
    let (defaults, _) = init();
    let n = 200;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 2.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(
        streamflow.sum() > 0.0,
        "Should produce positive flow in wet conditions"
    );
}

#[test]
fn test_dry_conditions_p_less_than_e() {
    let (defaults, _) = init();
    let n = 200;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 8.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions without numerical issues"
    );
}

#[test]
fn test_water_balance_monotonicity_in_pet() {
    // Halving PET should produce at least as much streamflow as full PET
    let (defaults, _) = init();
    let n = 500;
    let precip = helpers::generate_precipitation(n, 5.0, 0.5, 42);
    let pet_full = helpers::generate_pet(n, 4.0, 1.0, 43);
    let pet_half = pet_full.clone() * 0.5;

    let q_full =
        simulate(defaults.view(), precip.view(), pet_full.view()).unwrap();
    let q_half =
        simulate(defaults.view(), precip.view(), pet_half.view()).unwrap();
    assert!(
        q_half.sum() >= q_full.sum(),
        "Lower PET must not decrease total streamflow"
    );
}

#[test]
fn test_soil_nonlinearity_exponent_zero() {
    // x7 = 0 makes (S/x1)^x7 = 1 regardless of S, so Pr = P5 every sub-step
    let params = array![500.0, 500.0, 10.0, 50.0, 10.0, 20.0, 0.0, 50.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_soil_nonlinearity_exponent_high() {
    // x7 = 50 (maximum) makes the nonlinearity extreme — Pr is essentially
    // zero unless S is very close to x1
    let params =
        array![500.0, 500.0, 10.0, 50.0, 10.0, 20.0, 50.0, 50.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x8_threshold_zero() {
    // x8 = 0: Qr1 = R/x3 (full linear upper outflow, no threshold)
    let params = array![500.0, 500.0, 5.0, 50.0, 10.0, 20.0, 1.0, 0.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0);
}

#[test]
fn test_x8_threshold_maximum() {
    // x8 = 100: Qr1 only fires when R exceeds 100, otherwise Qr1 = 0
    let params =
        array![500.0, 500.0, 5.0, 50.0, 10.0, 20.0, 1.0, 100.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_qr1_never_fires_when_r_below_threshold() {
    // With huge x8 and dry conditions, R never exceeds the threshold
    // so the Qr1 branch is taken with pr - x8 < 0 (max(0, ...) clamps it).
    let params =
        array![500.0, 500.0, 1.0, 50.0, 10.0, 20.0, 1.0, 100.0, 20.0];
    let n = 100;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 1.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_percolation_capped_at_x5() {
    // Small x5 forces Ir = x5 < R every time percolation runs
    let params = array![500.0, 500.0, 10.0, 50.0, 1.0, 20.0, 1.0, 10.0, 10.0];
    let n = 200;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 2.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_percolation_drained_from_r() {
    // Large x5 (> typical R) means Ir = R every time, draining the
    // intermediate reservoir completely each step
    let params = array![500.0, 500.0, 10.0, 50.0, 20.0, 20.0, 1.0, 0.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 2.0, 0.5, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_groundwater_fast_emptying() {
    let params = array![500.0, 500.0, 10.0, 1.0, 10.0, 20.0, 1.0, 50.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_groundwater_slow_emptying() {
    let params =
        array![500.0, 500.0, 10.0, 100.0, 10.0, 20.0, 1.0, 50.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Triangular UH construction — edge cases
// =============================================================================

#[test]
fn test_uh_time_base_minimum() {
    // x6 = 2.0 (exact integer at lower bound): floor(2/2)=1 rising + 1 recession
    let params = array![500.0, 500.0, 10.0, 50.0, 10.0, 2.0, 1.0, 50.0, 10.0];
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_time_base_integer() {
    // x6 = 10.0 (exact integer mid-range)
    let params = array![500.0, 500.0, 10.0, 50.0, 10.0, 10.0, 1.0, 50.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_time_base_non_integer() {
    // x6 = 7.5: floor(7.5/2)=3 rising weights, ceil(7.5)=8 total length
    let params = array![500.0, 500.0, 10.0, 50.0, 10.0, 7.5, 1.0, 50.0, 10.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_time_base_maximum() {
    // x6 = 40 (upper bound) — long recession
    let params = array![500.0, 500.0, 10.0, 50.0, 10.0, 40.0, 1.0, 50.0, 10.0];
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 100.0f64..1000.0,
        x2 in 1.0f64..1000.0,
        x3 in 1.0f64..20.0,
        x4 in 1.0f64..100.0,
        x5 in 1.0f64..20.0,
        x6 in 2.0f64..40.0,
        x7 in 0.0f64..50.0,
        x8 in 0.0f64..100.0,
        x9 in 1.0f64..20.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8, x9];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let q = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(q.iter().all(|&v| v >= 0.0 && v.is_finite()));
    }

    #[test]
    fn prop_output_length(n in 10usize..200) {
        let (defaults, _) = init();
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

        let q = simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        prop_assert_eq!(q.len(), n);
    }

    #[test]
    fn prop_bound_corners_are_stable(
        // Exercise corners of the parameter box — the narrow lower bounds on
        // x2 and x9 are where numerical stability matters most.
        x1 in prop_oneof![Just(100.0), Just(1000.0)],
        x2 in prop_oneof![Just(1.0), Just(1000.0)],
        x3 in prop_oneof![Just(1.0), Just(20.0)],
        x4 in prop_oneof![Just(1.0), Just(100.0)],
        x5 in prop_oneof![Just(1.0), Just(20.0)],
        x6 in prop_oneof![Just(2.0), Just(40.0)],
        x7 in prop_oneof![Just(0.0), Just(50.0)],
        x8 in prop_oneof![Just(0.0), Just(100.0)],
        x9 in prop_oneof![Just(1.0), Just(20.0)],
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8, x9];
        let precip = helpers::generate_precipitation(100, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(100, 3.0, 1.0, 43);

        let q = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(q.iter().all(|&v| v.is_finite() && v >= 0.0));
    }
}
