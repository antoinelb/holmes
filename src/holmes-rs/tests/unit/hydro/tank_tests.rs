use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::tank::{init, param_descriptions, param_names, simulate};
use holmes_rs::hydro::HydroError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_init_bounds_shape() {
    let (defaults, bounds) = init();
    assert_eq!(defaults.len(), 7, "TANK model should have 7 parameters");
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
            "Parameter {}: lower ({}) must be < upper ({})",
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
            "Default for {} ({}) out of bounds [{}, {}]",
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

    // x1 (upper threshold): [1, 1000]
    assert_relative_eq!(bounds[[0, 0]], 1.0);
    assert_relative_eq!(bounds[[0, 1]], 1000.0);

    // x2 (lower threshold): [1, 1000]
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 1000.0);

    // x3 (fast emptying constant): [1, 100]
    assert_relative_eq!(bounds[[2, 0]], 1.0);
    assert_relative_eq!(bounds[[2, 1]], 100.0);

    // x4 (intermediate multiplier): [1, 100]
    assert_relative_eq!(bounds[[3, 0]], 1.0);
    assert_relative_eq!(bounds[[3, 1]], 100.0);

    // x5 (delay): [0.5, 5]
    assert_relative_eq!(bounds[[4, 0]], 0.5);
    assert_relative_eq!(bounds[[4, 1]], 5.0);

    // x6 (PET correction): [0.1, 2.0]
    assert_relative_eq!(bounds[[5, 0]], 0.1);
    assert_relative_eq!(bounds[[5, 1]], 2.0);

    // x7 (slow multiplier): [1, 100]
    assert_relative_eq!(bounds[[6, 0]], 1.0);
    assert_relative_eq!(bounds[[6, 1]], 100.0);
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
        assert_eq!(streamflow.len(), n, "Output length mismatch for n={}", n);
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

    assert!(streamflow.iter().all(|&q| q >= 0.0));
}

// =============================================================================
// Error Handling Tests
// =============================================================================

#[test]
fn test_simulate_param_count_error() {
    let wrong_params = array![10.0, 5.0, 2.0, 3.0]; // 4 params instead of 7
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(7, 4))));
}

#[test]
fn test_simulate_length_mismatch() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::LengthMismatch(3, 2))));
}

#[test]
fn test_tank_nan_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, f64::NAN, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NonFiniteInput { .. })));
}

#[test]
fn test_tank_negative_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, -5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NegativeInput { .. })));
}

#[test]
fn test_tank_nan_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, f64::NAN, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NonFiniteInput { .. })));
}

#[test]
fn test_tank_negative_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, -1.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NegativeInput { .. })));
}

#[test]
fn test_tank_empty_arrays() {
    let (defaults, _) = init();
    let precip: Array1<f64> = array![];
    let pet: Array1<f64> = array![];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::EmptyInput { .. })));
}

#[test]
fn test_tank_params_outside_bounds() {
    // x1 way above upper bound (1000)
    let params = array![5000.0, 50.0, 10.0, 5.0, 2.5, 1.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParameterOutOfBounds { .. })));
}

#[test]
fn test_tank_x3_below_lower_bound() {
    // x3 = 0.5 below lower (1.0) — would break the drain-safety invariant
    let params = array![100.0, 20.0, 0.5, 5.0, 2.5, 1.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParameterOutOfBounds { .. })));
}

// =============================================================================
// Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_x1_threshold_sensitivity() {
    // x1 = upper threshold — smaller x1 means Qs1 triggers earlier → more runoff
    let n = 100;
    let precip = Array1::from_elem(n, 30.0);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let small_threshold = array![5.0, 5.0, 10.0, 5.0, 2.5, 1.0, 5.0];
    let large_threshold = array![900.0, 5.0, 10.0, 5.0, 2.5, 1.0, 5.0];

    let flow_small =
        simulate(small_threshold.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(large_threshold.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
    assert!(
        flow_small.sum() > flow_large.sum(),
        "Smaller upper threshold should produce more total runoff"
    );
}

#[test]
fn test_x6_pet_correction_sensitivity() {
    // x6 is the PET correction — higher x6 → more ET → less streamflow
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low_et = array![100.0, 20.0, 10.0, 5.0, 2.5, 0.2, 5.0];
    let params_high_et = array![100.0, 20.0, 10.0, 5.0, 2.5, 1.8, 5.0];

    let flow_low = simulate(params_low_et.view(), precip.view(), pet.view())
        .unwrap();
    let flow_high =
        simulate(params_high_et.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
    assert!(
        flow_low.sum() > flow_high.sum(),
        "Lower PET correction should produce more streamflow"
    );
}

#[test]
fn test_x7_slow_multiplier() {
    // x7 controls the slow reservoir: Ql = L/(x3·x4·x7²)
    let n = 365;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![100.0, 20.0, 5.0, 2.0, 2.5, 1.0, 1.0];
    let params_slow = array![100.0, 20.0, 5.0, 2.0, 2.5, 1.0, 50.0];

    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Branch Coverage Tests
// =============================================================================

#[test]
fn test_wet_conditions_p_greater_than_e() {
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 5.0);

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
    let n = 100;
    let precip = Array1::from_elem(n, 1.0);
    let pet = Array1::from_elem(n, 10.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_upper_threshold_not_exceeded() {
    // Large x1 + moderate precip → Qs1 stays 0, only Qs2 and Is fire
    let n = 100;
    let precip = Array1::from_elem(n, 3.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![1000.0, 1.0, 10.0, 5.0, 2.5, 1.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_upper_threshold_exceeded() {
    // Small x1+x2 + high precip → Qs1 triggers
    let n = 100;
    let precip = Array1::from_elem(n, 100.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![2.0, 1.0, 5.0, 2.0, 2.5, 1.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0);
}

#[test]
fn test_lower_threshold_not_exceeded() {
    // Very large x2 → Qs2 stays 0 for R and T reservoirs too
    let n = 100;
    let precip = Array1::from_elem(n, 1.0);
    let pet = Array1::from_elem(n, 0.5);

    let params = array![500.0, 900.0, 50.0, 50.0, 2.5, 0.5, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_reservoirs_dry_to_zero() {
    // Heavy ET cascade, no precipitation — reservoirs clamp via min(E, storage)
    let n = 200;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 20.0);

    let (defaults, _) = init();
    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_short() {
    // x5 at minimum (0.5)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![100.0, 20.0, 10.0, 5.0, 0.5, 1.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    // x5 at maximum (5.0)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![100.0, 20.0, 10.0, 5.0, 5.0, 1.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_integer() {
    // x5 = 2.0 (exact integer) — edge case in delay vector construction
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![100.0, 20.0, 10.0, 5.0, 2.0, 1.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_groundwater_extreme_recession() {
    // x7 very large → groundwater drains extremely slowly via L/(x3·x4·x7²)
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![100.0, 20.0, 1.0, 1.0, 2.5, 1.0, 1.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));

    let params_slow = array![100.0, 20.0, 100.0, 100.0, 2.5, 1.0, 100.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 1.0f64..1000.0,
        x2 in 1.0f64..1000.0,
        x3 in 1.0f64..100.0,
        x4 in 1.0f64..100.0,
        x5 in 0.5f64..5.0,
        x6 in 0.1f64..2.0,
        x7 in 1.0f64..100.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow =
            simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q >= 0.0));
    }

    #[test]
    fn prop_output_length(n in 10usize..200) {
        let (defaults, _) = init();
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

        let streamflow =
            simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        prop_assert_eq!(streamflow.len(), n);
    }

    #[test]
    fn prop_finite_output(
        x1 in 10.0f64..500.0,
        x2 in 1.0f64..100.0,
        x3 in 1.0f64..50.0,
        x4 in 1.0f64..20.0,
        x5 in 1.0f64..4.0,
        x6 in 0.3f64..1.5,
        x7 in 1.0f64..20.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow =
            simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite()));
    }
}
