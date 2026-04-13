use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::simhyd::{
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
    assert_eq!(defaults.len(), 8, "SIMHYD model should have 8 parameters");
    assert_eq!(
        bounds.shape(),
        &[8, 2],
        "Bounds should be 8x2 (params x [lower, upper])"
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
    assert_eq!(param_names.len(), 8);
    assert_eq!(
        param_names,
        &["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"]
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

    // x1 (interception store capacity): [0.5, 10]
    assert_relative_eq!(bounds[[0, 0]], 0.5);
    assert_relative_eq!(bounds[[0, 1]], 10.0);

    // x2 (soil moisture store capacity): [1, 500]
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 500.0);

    // x3 (ground reservoir emptying constant): [1, 1000]
    assert_relative_eq!(bounds[[2, 0]], 1.0);
    assert_relative_eq!(bounds[[2, 1]], 1000.0);

    // x4 (delay): [0.5, 5]
    assert_relative_eq!(bounds[[3, 0]], 0.5);
    assert_relative_eq!(bounds[[3, 1]], 5.0);

    // x5 (routing reservoir emptying constant): [1, 500]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 500.0);

    // x6 (interflow constant): [1, 1000]
    assert_relative_eq!(bounds[[5, 0]], 1.0);
    assert_relative_eq!(bounds[[5, 1]], 1000.0);

    // x7 (groundwater recharge constant): [1, 1000]
    assert_relative_eq!(bounds[[6, 0]], 1.0);
    assert_relative_eq!(bounds[[6, 1]], 1000.0);

    // x8 (maximum infiltration capacity): [1, 500]
    assert_relative_eq!(bounds[[7, 0]], 1.0);
    assert_relative_eq!(bounds[[7, 1]], 500.0);
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
    let wrong_params = array![5.0, 250.0, 500.0, 2.5]; // Only 4 params instead of 8
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(8, 4))));
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
fn test_simhyd_nan_input() {
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
fn test_simhyd_negative_precipitation() {
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
fn test_simhyd_nan_pet() {
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
fn test_simhyd_negative_pet() {
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
fn test_simhyd_empty_arrays() {
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
fn test_simhyd_params_outside_bounds() {
    // x1 below lower bound (0.5)
    let params = array![0.1, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 250.0];
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
fn test_x1_interception_sensitivity() {
    // x1 controls interception capacity: higher x1 → more interception → less runoff
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small =
        array![0.5, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 250.0];
    let params_large =
        array![10.0, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 250.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x2_soil_capacity_sensitivity() {
    // x2 controls soil moisture capacity: higher x2 → more storage → less runoff initially
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small =
        array![5.0, 10.0, 500.0, 2.5, 250.0, 500.0, 500.0, 250.0];
    let params_large =
        array![5.0, 490.0, 500.0, 2.5, 250.0, 500.0, 500.0, 250.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x5_routing_sensitivity() {
    // x5 controls routing reservoir emptying: higher x5 → slower routing
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast =
        array![5.0, 250.0, 500.0, 2.5, 1.0, 500.0, 500.0, 250.0];
    let params_slow =
        array![5.0, 250.0, 500.0, 2.5, 490.0, 500.0, 500.0, 250.0];

    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_fast.iter().all(|&q| q.is_finite()));
    assert!(flow_slow.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x8_infiltration_sensitivity() {
    // x8 controls max infiltration: higher x8 → more infiltration → less surface runoff
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low_inf =
        array![5.0, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 1.0];
    let params_high_inf =
        array![5.0, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 490.0];

    let flow_low =
        simulate(params_low_inf.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high_inf.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 0.5f64..10.0,
        x2 in 1.0f64..500.0,
        x3 in 1.0f64..1000.0,
        x4 in 0.5f64..5.0,
        x5 in 1.0f64..500.0,
        x6 in 1.0f64..1000.0,
        x7 in 1.0f64..1000.0,
        x8 in 1.0f64..500.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8];
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
        x1 in 1.0f64..9.0,
        x2 in 50.0f64..450.0,
        x3 in 50.0f64..900.0,
        x4 in 1.0f64..4.0,
        x5 in 50.0f64..450.0,
        x6 in 50.0f64..900.0,
        x7 in 50.0f64..900.0,
        x8 in 50.0f64..450.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8];
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
fn test_wet_conditions_high_precipitation() {
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 2.0);

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
fn test_dry_conditions_low_precipitation() {
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 10.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions without numerical issues"
    );
}

#[test]
fn test_soil_excess_triggers() {
    // Small x2 with high precipitation: soil fills quickly, triggering excess
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![1.0, 5.0, 500.0, 2.5, 250.0, 1.0, 1.0, 400.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0, "Excess should produce runoff");
}

#[test]
fn test_no_soil_excess() {
    // Large x2 with low precipitation: soil never fills
    let n = 50;
    let precip = Array1::from_elem(n, 0.1);
    let pet = Array1::from_elem(n, 3.0);

    let params = array![5.0, 500.0, 500.0, 2.5, 250.0, 500.0, 500.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_soil_dries_to_zero() {
    // Heavy PET, no precipitation — soil should clamp at 0
    let n = 200;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 20.0);

    let (defaults, _) = init();
    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle soil drying to zero without numerical issues"
    );
}

#[test]
fn test_interception_exceeds_rainfall() {
    // P < min(x1, E): all precipitation is intercepted
    let n = 50;
    let precip = Array1::from_elem(n, 0.1); // Very low P
    let pet = Array1::from_elem(n, 5.0); // High PET

    let params = array![10.0, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_surface_runoff_dominates() {
    // Very low x8 (max infiltration) forces surface runoff
    let n = 100;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![1.0, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 1.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle surface runoff dominated regime"
    );
    assert!(streamflow.sum() > 0.0);
}

#[test]
fn test_delay_parameter_short() {
    // x4 at minimum (0.5) — short delay
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![5.0, 250.0, 500.0, 0.5, 250.0, 500.0, 500.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    // x4 at maximum (5.0) — long delay
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![5.0, 250.0, 500.0, 5.0, 250.0, 500.0, 500.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_integer() {
    // x4 = 2.0 (exact integer) — edge case in delay vector construction
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![5.0, 250.0, 500.0, 2.0, 250.0, 500.0, 500.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_ground_reservoir_extreme_slow() {
    // x3 at maximum (1000) — very slow ground reservoir emptying
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![5.0, 250.0, 1000.0, 2.5, 250.0, 500.0, 500.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_ground_reservoir_fast() {
    // x3 at minimum (1) — fast ground reservoir emptying
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![5.0, 250.0, 1.0, 2.5, 250.0, 500.0, 500.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_interflow_dominant() {
    // Small x6 → high interflow proportion
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![5.0, 250.0, 500.0, 2.5, 250.0, 1.0, 500.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_groundwater_recharge_dominant() {
    // Small x7 → high groundwater recharge
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![5.0, 250.0, 500.0, 2.5, 250.0, 500.0, 1.0, 250.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_infiltration_all_goes_through() {
    // High x8, low excess: all excess infiltrates (FILT = EXC path)
    let n = 100;
    let precip = Array1::from_elem(n, 3.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![1.0, 250.0, 500.0, 2.5, 250.0, 500.0, 500.0, 500.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_high_precipitation_stress() {
    // Very high precipitation to stress all reservoirs
    let n = 100;
    let precip = Array1::from_elem(n, 200.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![0.5, 50.0, 10.0, 2.5, 10.0, 5.0, 5.0, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle extreme precipitation without numerical issues"
    );
}
