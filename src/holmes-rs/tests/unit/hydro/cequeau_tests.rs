use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::cequeau::{
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
    assert_eq!(defaults.len(), 9, "CEQUEAU should have 9 parameters");
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

    // x1: infiltration threshold [0, 3000]
    assert_relative_eq!(bounds[[0, 0]], 0.0);
    assert_relative_eq!(bounds[[0, 1]], 3000.0);

    // x2: soil reservoir drainage threshold [1, 3000]
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 3000.0);

    // x3: infiltration constant [1, 100]
    assert_relative_eq!(bounds[[2, 0]], 1.0);
    assert_relative_eq!(bounds[[2, 1]], 100.0);

    // x4: upper lateral drainage constant [1, 50]
    assert_relative_eq!(bounds[[3, 0]], 1.0);
    assert_relative_eq!(bounds[[3, 1]], 50.0);

    // x5: max soil reservoir capacity [1, 8000]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 8000.0);

    // x6: delay [0.1, 20]
    assert_relative_eq!(bounds[[5, 0]], 0.1);
    assert_relative_eq!(bounds[[5, 1]], 20.0);

    // x7: groundwater drainage threshold [0.01, 500]
    assert_relative_eq!(bounds[[6, 0]], 0.01);
    assert_relative_eq!(bounds[[6, 1]], 500.0);

    // x8: lower lateral drainage constant [1, 1000]
    assert_relative_eq!(bounds[[7, 0]], 1.0);
    assert_relative_eq!(bounds[[7, 1]], 1000.0);

    // x9: lower groundwater drainage constant [1, 3000]
    assert_relative_eq!(bounds[[8, 0]], 1.0);
    assert_relative_eq!(bounds[[8, 1]], 3000.0);
}

#[test]
fn test_init_defaults_are_midpoints() {
    // Defaults are computed as midpoint of bounds: (lower + upper) / 2
    let (defaults, bounds) = init();

    for i in 0..9 {
        let expected_midpoint = (bounds[[i, 0]] + bounds[[i, 1]]) / 2.0;
        assert_relative_eq!(defaults[i], expected_midpoint, epsilon = 1e-10,);
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

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q >= 0.0),
        "All values should be non-negative"
    );

    // With no precipitation, flow should decay toward zero
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
    // Use params with short delay to get clear event response
    let params = array![100.0, 100.0, 10.0, 5.0, 500.0, 1.0, 50.0, 50.0, 50.0];
    let n = 80;

    // Single precipitation event at day 10
    let mut precip = Array1::zeros(n);
    precip[10] = 100.0;
    let pet = Array1::from_elem(n, 2.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    // Flow should increase after precipitation event
    let pre_event_flow = streamflow[9];
    let post_event_max = streamflow
        .slice(ndarray::s![10..30])
        .iter()
        .cloned()
        .fold(f64::NEG_INFINITY, f64::max);

    assert!(
        post_event_max > pre_event_flow,
        "Flow should increase after precipitation event (pre: {}, post_max: {})",
        pre_event_flow,
        post_event_max
    );

    // Flow should eventually decrease well after the event response
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
    let wrong_params = array![100.0, 0.5, 50.0, 3.0]; // Only 4 params instead of 9
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(9, 4))));
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
fn test_cequeau_params_outside_bounds() {
    // x1 upper bound is 3000, so 3500 is out of bounds
    let params = array![
        3500.0, 1500.5, 50.5, 25.5, 4000.5, 10.05, 250.005, 500.5, 1500.5
    ];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject out-of-bounds parameters"
    );
}

#[test]
fn test_cequeau_negative_precipitation() {
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
fn test_cequeau_nan_in_precipitation() {
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
fn test_cequeau_infinity_in_pet() {
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
fn test_cequeau_empty_arrays() {
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
// Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_x1_sensitivity() {
    // x1 controls infiltration threshold
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low =
        array![10.0, 100.0, 10.0, 5.0, 500.0, 3.0, 50.0, 50.0, 50.0];
    let params_high =
        array![2500.0, 100.0, 10.0, 5.0, 500.0, 3.0, 50.0, 50.0, 50.0];

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x5_sensitivity() {
    // x5 controls max soil reservoir capacity
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small =
        array![100.0, 100.0, 10.0, 5.0, 10.0, 3.0, 50.0, 50.0, 50.0];
    let params_large =
        array![100.0, 100.0, 10.0, 5.0, 5000.0, 3.0, 50.0, 50.0, 50.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x6_sensitivity() {
    // x6 controls delay in days
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_short =
        array![100.0, 100.0, 10.0, 5.0, 500.0, 0.5, 50.0, 50.0, 50.0];
    let params_long =
        array![100.0, 100.0, 10.0, 5.0, 500.0, 15.0, 50.0, 50.0, 50.0];

    let flow_short =
        simulate(params_short.view(), precip.view(), pet.view()).unwrap();
    let flow_long =
        simulate(params_long.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_short.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_long.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 0.0f64..500.0,
        x2 in 1.0f64..500.0,
        x3 in 1.0f64..100.0,
        x4 in 1.0f64..50.0,
        x5 in 1.0f64..8000.0,
        x6 in 0.1f64..20.0,
        x7 in 0.01f64..500.0,
        x8 in 1.0f64..1000.0,
        x9 in 1.0f64..3000.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8, x9];
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
        x1 in 10.0f64..400.0,
        x2 in 5.0f64..400.0,
        x3 in 2.0f64..80.0,
        x4 in 2.0f64..40.0,
        x5 in 10.0f64..5000.0,
        x6 in 0.5f64..15.0,
        x7 in 1.0f64..400.0,
        x8 in 5.0f64..800.0,
        x9 in 5.0f64..2500.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8, x9];
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
fn test_precipitation_equals_pet() {
    let (defaults, _) = init();
    let n = 50;
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
    // Dry conditions where PET > precipitation
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 1.0);
    let pet = Array1::from_elem(n, 5.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions"
    );
}

#[test]
fn test_high_precipitation_low_pet() {
    // Wet conditions where precipitation >> PET
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 1.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle wet conditions"
    );
    assert!(
        streamflow.sum() > 0.0,
        "Should produce positive total flow with high precipitation"
    );
}

#[test]
fn test_percolation_branch() {
    // Surface store exceeds x1, triggering percolation (low x1)
    let params = array![10.0, 100.0, 6.0, 5.0, 500.0, 3.0, 50.0, 50.0, 50.0];
    let n = 100;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 1.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle percolation correctly"
    );
}

#[test]
fn test_surface_overflow_branch() {
    // Surface store exceeds x5, triggering overflow streamflow (very small x5)
    let params = array![100.0, 100.0, 10.0, 5.0, 5.0, 3.0, 50.0, 50.0, 50.0];
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 1.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle surface overflow correctly"
    );
}

#[test]
fn test_surface_drainage_threshold_branch() {
    // Surface store exceeds x2, triggering surface drainage (low x2)
    let params = array![100.0, 10.0, 10.0, 5.0, 500.0, 3.0, 50.0, 50.0, 50.0];
    let n = 100;
    let precip = Array1::from_elem(n, 30.0);
    let pet = Array1::from_elem(n, 1.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle surface drainage threshold correctly"
    );
}

#[test]
fn test_groundwater_drainage_threshold_branch() {
    // Groundwater store exceeds x7, triggering groundwater drainage (low x7, low x3 for fast percolation)
    let params = array![10.0, 100.0, 1.0, 5.0, 500.0, 3.0, 5.0, 50.0, 50.0];
    let n = 100;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 1.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle groundwater drainage threshold correctly"
    );
}

#[test]
fn test_delay_line_edge_cases() {
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // x6 near minimum (0.1) - very short delay
    let params_min =
        array![100.0, 100.0, 10.0, 5.0, 500.0, 0.1, 50.0, 50.0, 50.0];
    let flow_min =
        simulate(params_min.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_min.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x6 near maximum (20.0) - long delay
    let params_max =
        array![100.0, 100.0, 10.0, 5.0, 500.0, 20.0, 50.0, 50.0, 50.0];
    let flow_max =
        simulate(params_max.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_max.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_groundwater_pet_branch() {
    // Ensure groundwater PET is exercised: remaining_pet > 0 and gw_store > 0
    // Use high PET so surface can't absorb it all, leaving remaining_pet
    let params = array![10.0, 100.0, 1.0, 5.0, 100.0, 3.0, 50.0, 50.0, 50.0];
    let n = 100;
    let precip = Array1::from_elem(n, 15.0);
    let pet = Array1::from_elem(n, 10.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle groundwater PET correctly"
    );
}

#[test]
fn test_x8_extreme_values() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // Low x8 - fast lateral drainage
    let params_low =
        array![100.0, 100.0, 10.0, 5.0, 500.0, 3.0, 50.0, 1.0, 50.0];
    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_low.iter().all(|&q| q.is_finite() && q >= 0.0));

    // High x8 - slow lateral drainage
    let params_high =
        array![100.0, 100.0, 10.0, 5.0, 500.0, 3.0, 50.0, 1000.0, 50.0];
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_high.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x9_extreme_values() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // Low x9 - fast groundwater drainage
    let params_low =
        array![100.0, 100.0, 10.0, 5.0, 500.0, 3.0, 50.0, 50.0, 1.0];
    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_low.iter().all(|&q| q.is_finite() && q >= 0.0));

    // High x9 - slow groundwater drainage
    let params_high =
        array![100.0, 100.0, 10.0, 5.0, 500.0, 3.0, 50.0, 50.0, 3000.0];
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_high.iter().all(|&q| q.is_finite() && q >= 0.0));
}
