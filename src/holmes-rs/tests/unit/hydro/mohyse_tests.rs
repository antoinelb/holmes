use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::mohyse::{
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
    assert_eq!(defaults.len(), 7, "MOHYSE model should have 7 parameters");
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

    // x1 (transpiration coefficient): [0.01, 1.0]
    assert_relative_eq!(bounds[[0, 0]], 0.01);
    assert_relative_eq!(bounds[[0, 1]], 1.0);

    // x2 (maximum infiltration capacity): [1, 2000]
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 2000.0);

    // x3 (aquifer vadose emptying): [0.001, 1.0]
    assert_relative_eq!(bounds[[2, 0]], 0.001);
    assert_relative_eq!(bounds[[2, 1]], 1.0);

    // x4 (river vadose emptying): [0.001, 1.0]
    assert_relative_eq!(bounds[[3, 0]], 0.001);
    assert_relative_eq!(bounds[[3, 1]], 1.0);

    // x5 (aquifer emptying): [0.001, 1.0]
    assert_relative_eq!(bounds[[4, 0]], 0.001);
    assert_relative_eq!(bounds[[4, 1]], 1.0);

    // x6 (UH shape alpha): [1.0, 5.0]
    assert_relative_eq!(bounds[[5, 0]], 1.0);
    assert_relative_eq!(bounds[[5, 1]], 5.0);

    // x7 (UH scale beta): [0.5, 5.0]
    assert_relative_eq!(bounds[[6, 0]], 0.5);
    assert_relative_eq!(bounds[[6, 1]], 5.0);
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
    let wrong_params = array![0.5, 500.0, 0.1, 0.1]; // Only 4 params instead of 7
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
fn test_mohyse_nan_input() {
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
fn test_mohyse_negative_precipitation() {
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
fn test_mohyse_nan_pet() {
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
fn test_mohyse_negative_pet() {
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
fn test_mohyse_empty_arrays() {
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
fn test_mohyse_params_outside_bounds() {
    // x1 way above upper bound (1.0)
    let params = array![5.0, 500.0, 0.1, 0.1, 0.1, 3.0, 2.5];
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
fn test_x1_transpiration_sensitivity() {
    // x1 controls transpiration: TR = min(x1*S, E-ED)
    // Higher x1 means more transpiration → less streamflow
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![0.01, 1000.0, 0.1, 0.1, 0.1, 2.0, 2.0]; // Low transpiration
    let params_high = array![0.9, 1000.0, 0.1, 0.1, 0.1, 2.0, 2.0]; // High transpiration

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
    assert!(
        flow_low.sum() > flow_high.sum(),
        "Lower transpiration should produce more streamflow"
    );
}

#[test]
fn test_x2_capacity_sensitivity() {
    // x2 controls infiltration capacity: I = (P-ED)*(1 - S/x2) when S < x2
    // Higher x2 → more infiltration → less surface runoff (but more GW later)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small = array![0.1, 10.0, 0.1, 0.1, 0.1, 2.0, 2.0]; // Small capacity
    let params_large = array![0.1, 1500.0, 0.1, 0.1, 0.1, 2.0, 2.0]; // Large capacity

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x5_groundwater_sensitivity() {
    // x5 controls groundwater emptying: Q3 = x5 * R
    // Higher x5 → faster GW release → quicker response
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_slow = array![0.1, 1000.0, 0.1, 0.1, 0.001, 2.0, 2.0]; // Slow GW
    let params_fast = array![0.1, 1000.0, 0.1, 0.1, 0.9, 2.0, 2.0]; // Fast GW

    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_slow.iter().all(|&q| q.is_finite()));
    assert!(flow_fast.iter().all(|&q| q.is_finite()));
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
fn test_soil_saturated_no_infiltration() {
    // When S >= x2, I = 0 — everything becomes surface runoff
    let n = 100;
    let precip = Array1::from_elem(n, 50.0); // High precip
    let pet = Array1::from_elem(n, 2.0);

    // Very small x2 (capacity) forces S >= x2 quickly → I = 0 branch
    let params = array![0.01, 1.0, 0.001, 0.001, 0.1, 2.0, 2.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0, "Saturation should produce runoff");
}

#[test]
fn test_soil_unsaturated_infiltration() {
    // Large x2 keeps S < x2 — infiltration occurs
    let n = 50;
    let precip = Array1::from_elem(n, 5.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![0.1, 2000.0, 0.1, 0.1, 0.1, 2.0, 2.0]; // Large capacity
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_soil_dries_to_zero() {
    // Heavy ET, no precipitation — soil should clamp at 0 via .max(0.0)
    let n = 200;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 20.0); // Very high PET

    let (defaults, _) = init();
    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle soil drying to zero without numerical issues"
    );
}

#[test]
fn test_uh_shape_exponential() {
    // x6 = 1.0 (minimum) → UH is pure exponential decay
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.1, 1000.0, 0.1, 0.1, 0.1, 1.0, 2.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_shape_bell() {
    // x6 = 5.0 (maximum) → bell-shaped UH with delayed peak
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.1, 1000.0, 0.1, 0.1, 0.1, 5.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_scale_short() {
    // x7 = 0.5 (minimum) → concentrated UH, fast response
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.1, 1000.0, 0.1, 0.1, 0.1, 2.0, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_scale_long() {
    // x7 = 5.0 (maximum) → spread-out UH, slow response
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.1, 1000.0, 0.1, 0.1, 0.1, 2.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_equal_precip_and_pet() {
    // When P = E exactly, ED = P = E, so P-ED = 0 and E-ED = 0
    let n = 100;
    let precip = Array1::from_elem(n, 5.0);
    let pet = Array1::from_elem(n, 5.0);

    let (defaults, _) = init();
    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle P = E edge case"
    );
}

#[test]
fn test_high_drainage_coefficients() {
    // x3 and x4 near 1.0 — soil drains very fast each step
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.1, 1000.0, 0.9, 0.9, 0.5, 2.0, 2.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_minimal_drainage_coefficients() {
    // x3 and x4 near 0.001 — soil drains very slowly
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.1, 1000.0, 0.001, 0.001, 0.001, 2.0, 2.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_high_inflow_stress() {
    // Very high precipitation to stress all pathways
    let n = 100;
    let precip = Array1::from_elem(n, 200.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![0.1, 50.0, 0.5, 0.5, 0.5, 2.0, 2.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle extreme precipitation"
    );
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 0.01f64..1.0,
        x2 in 1.0f64..2000.0,
        x3 in 0.001f64..1.0,
        x4 in 0.001f64..1.0,
        x5 in 0.001f64..1.0,
        x6 in 1.0f64..5.0,
        x7 in 0.5f64..5.0
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
        x1 in 0.05f64..0.8,
        x2 in 50.0f64..1500.0,
        x3 in 0.01f64..0.8,
        x4 in 0.01f64..0.8,
        x5 in 0.01f64..0.8,
        x6 in 1.0f64..4.5,
        x7 in 0.5f64..4.5
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite()));
    }
}
