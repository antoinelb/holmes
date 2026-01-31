use crate::helpers;
use holmes_rs::hydro::gr4j::{init, param_descriptions, param_names, simulate};
use holmes_rs::hydro::utils::validate_output;
use holmes_rs::hydro::HydroError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_init_bounds_shape() {
    let (defaults, bounds) = init();
    assert_eq!(defaults.len(), 4, "GR4J should have 4 parameters");
    assert_eq!(
        bounds.shape(),
        &[4, 2],
        "Bounds should be 4x2 (params x [lower, upper])"
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
    assert_eq!(param_names.len(), 4);
    assert_eq!(param_names, &["x1", "x2", "x3", "x4"]);
}

#[test]
fn test_param_descriptions() {
    assert_eq!(param_descriptions.len(), param_names.len());
    for desc in param_descriptions {
        assert!(!desc.is_empty(), "Description should not be empty");
    }
}

// =============================================================================
// Simulation Tests
// =============================================================================

#[test]
fn test_simulate_default_params() {
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
}

#[test]
fn test_simulate_zero_precipitation() {
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::zeros(n);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    // With no precipitation, flow should decay toward zero
    assert_eq!(streamflow.len(), n);
    // Last values should be lower than first (decay)
    let first_half_mean: f64 =
        streamflow.slice(ndarray::s![..n / 2]).mean().unwrap();
    let last_half_mean: f64 =
        streamflow.slice(ndarray::s![n / 2..]).mean().unwrap();
    assert!(
        last_half_mean <= first_half_mean + 0.01,
        "Flow should decay with zero precipitation"
    );
}

#[test]
fn test_simulate_single_event() {
    let (defaults, _) = init();
    let n = 50;

    // Single precipitation event at day 10
    let mut precip = Array1::zeros(n);
    precip[10] = 50.0;
    let pet = Array1::from_elem(n, 2.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    // Flow should increase after precipitation event
    let pre_event_flow = streamflow[9];
    let post_event_max = streamflow
        .slice(ndarray::s![10..20])
        .iter()
        .cloned()
        .fold(f64::NEG_INFINITY, f64::max);

    assert!(
        post_event_max > pre_event_flow,
        "Flow should increase after precipitation event (pre: {}, post_max: {})",
        pre_event_flow,
        post_event_max
    );

    // Flow should eventually decrease after the event response
    let late_flow = streamflow[n - 1];
    assert!(
        late_flow < post_event_max,
        "Flow should decrease after event response (max: {}, late: {})",
        post_event_max,
        late_flow
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
    let wrong_params = array![100.0, 0.5, 50.0]; // Only 3 params instead of 4
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(4, 3))));
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
fn test_x1_sensitivity() {
    // x1 controls production store capacity
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low_x1 = array![100.0, 0.0, 100.0, 2.0]; // Small production store
    let params_high_x1 = array![1000.0, 0.0, 100.0, 2.0]; // Large production store

    let flow_low =
        simulate(params_low_x1.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high_x1.view(), precip.view(), pet.view()).unwrap();

    // Both should produce valid output
    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x4_sensitivity() {
    // x4 controls unit hydrograph time base
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_short = array![300.0, 0.0, 100.0, 1.0]; // Quick response
    let params_long = array![300.0, 0.0, 100.0, 5.0]; // Slow response

    let flow_short =
        simulate(params_short.view(), precip.view(), pet.view()).unwrap();
    let flow_long =
        simulate(params_long.view(), precip.view(), pet.view()).unwrap();

    // Both should produce valid output
    assert!(flow_short.iter().all(|&q| q.is_finite()));
    assert!(flow_long.iter().all(|&q| q.is_finite()));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 10.0f64..1500.0,
        x2 in -5.0f64..3.0,
        x3 in 10.0f64..400.0,
        x4 in 0.8f64..10.0
    ) {
        let params = array![x1, x2, x3, x4];
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
        x2 in -3.0f64..2.0,
        x3 in 50.0f64..300.0,
        x4 in 1.0f64..8.0
    ) {
        let params = array![x1, x2, x3, x4];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite()));
    }
}

// =============================================================================
// Anti-Fragility Tests - Input Validation
// =============================================================================

#[test]
fn test_gr4j_params_outside_bounds() {
    // Parameters outside valid bounds
    let params = array![5000.0, 10.0, 1.0, 0.1]; // All outside bounds
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject out-of-bounds parameters"
    );
}

#[test]
fn test_gr4j_negative_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, -5.0, 0.0]; // Negative precipitation (physically invalid)
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NegativeInput { .. })),
        "Should reject negative precipitation"
    );
}

#[test]
fn test_gr4j_nan_in_precipitation() {
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
fn test_gr4j_infinity_in_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, f64::INFINITY, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NonFiniteInput { .. })),
        "Should reject infinity in PET"
    );
}

#[test]
fn test_gr4j_empty_arrays() {
    let (defaults, _) = init();
    let precip: Array1<f64> = array![];
    let pet: Array1<f64> = array![];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::EmptyInput { .. })),
        "Should reject empty input arrays"
    );
}

// =============================================================================
// Branch Coverage Tests
// =============================================================================

#[test]
fn test_precipitation_equals_pet() {
    // Test the case where precipitation == pet (no net precip or net PET)
    let (defaults, _) = init();
    let n = 50;
    // Create arrays where precip equals pet at several points
    let precip = Array1::from_elem(n, 5.0);
    let pet = Array1::from_elem(n, 5.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle p == pet case"
    );
}

#[test]
fn test_high_pet_low_precipitation() {
    // Test dry conditions where PET > precipitation
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 1.0); // Low precipitation
    let pet = Array1::from_elem(n, 5.0); // High PET

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions"
    );
}

#[test]
fn test_high_precipitation_low_pet() {
    // Test wet conditions where precipitation >> PET
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 50.0); // High precipitation
    let pet = Array1::from_elem(n, 1.0); // Low PET

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle wet conditions"
    );
    // Total flow should be significant with high precipitation
    assert!(
        streamflow.sum() > 0.0,
        "Should produce positive total flow with high precipitation"
    );
}

#[test]
fn test_percolation_branch() {
    // Test that percolation branch is exercised with filled production store
    let params = array![100.0, 0.0, 100.0, 2.0]; // Small x1 (production store capacity)
    let n = 100;
    let precip = Array1::from_elem(n, 20.0); // Consistent high precipitation
    let pet = Array1::from_elem(n, 1.0); // Low PET

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle percolation correctly"
    );
}

#[test]
fn test_unit_hydrograph_edge_cases() {
    // Test with x4 at boundary values
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // x4 = 0.8 (minimum bound) - very short unit hydrograph
    let params_min = array![300.0, 0.0, 100.0, 0.8];
    let flow_min =
        simulate(params_min.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_min.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x4 = 10.0 (maximum bound) - very long unit hydrograph
    let params_max = array![300.0, 0.0, 100.0, 10.0];
    let flow_max =
        simulate(params_max.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_max.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x2_negative_exchange() {
    // Test with negative x2 (water export to groundwater)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![300.0, -5.0, 100.0, 2.0]; // Negative x2
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle negative groundwater exchange"
    );
}

#[test]
fn test_x2_positive_exchange() {
    // Test with positive x2 (water import from groundwater)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![300.0, 3.0, 100.0, 2.0]; // Positive x2
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle positive groundwater exchange"
    );
}

#[test]
#[ignore = "R5-NUM-05: Potential numerical instability with extreme x1"]
fn test_gr4j_extreme_x1() {
    // Very small x1 can cause numerical issues
    let params = array![10.0, 0.0, 100.0, 2.0]; // x1 at minimum bound
    let precip = helpers::generate_precipitation(100, 50.0, 0.5, 42); // Heavy precipitation
    let pet = helpers::generate_pet(100, 1.0, 0.5, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(
        streamflow.iter().all(|&q| q.is_finite()),
        "Should handle extreme x1 without numerical issues"
    );
}

// =============================================================================
// Direct Utility Function Tests
// =============================================================================

#[test]
fn test_validate_output_nan() {
    let arr = array![1.0, f64::NAN, 3.0];
    let result = validate_output(arr.view(), "test");
    assert!(
        matches!(
            result,
            Err(HydroError::NumericalError {
                context: "test",
                ..
            })
        ),
        "Should reject NaN in output"
    );
}

#[test]
fn test_validate_output_infinity() {
    let arr = array![1.0, f64::INFINITY, 3.0];
    let result = validate_output(arr.view(), "test context");
    assert!(
        matches!(
            result,
            Err(HydroError::NumericalError {
                context: "test context",
                ..
            })
        ),
        "Should reject Infinity in output"
    );
}

#[test]
fn test_validate_output_valid() {
    let arr = array![1.0, 2.0, 3.0];
    let result = validate_output(arr.view(), "test");
    assert!(result.is_ok(), "Should accept valid output");
}
