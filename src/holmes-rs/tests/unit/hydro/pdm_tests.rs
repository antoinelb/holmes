use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::pdm::{
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
    assert_eq!(defaults.len(), 8, "PDM model should have 8 parameters");
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

    // x1 (Cmax): [10, 2000]
    assert_relative_eq!(bounds[[0, 0]], 10.0);
    assert_relative_eq!(bounds[[0, 1]], 2000.0);

    // x2 (b, spatial variability): [0.01, 2.0]
    assert_relative_eq!(bounds[[1, 0]], 0.01);
    assert_relative_eq!(bounds[[1, 1]], 2.0);

    // x3 (Alpha, drainage threshold fraction): [0.01, 0.99]
    assert_relative_eq!(bounds[[2, 0]], 0.01);
    assert_relative_eq!(bounds[[2, 1]], 0.99);

    // x4 (delay): [0.5, 5.0]
    assert_relative_eq!(bounds[[3, 0]], 0.5);
    assert_relative_eq!(bounds[[3, 1]], 5.0);

    // x5 (cubic ground reservoir): [1, 2000]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 2000.0);

    // x6 (linear routing constant): [1, 30]
    assert_relative_eq!(bounds[[5, 0]], 1.0);
    assert_relative_eq!(bounds[[5, 1]], 30.0);

    // x7 (rainfall correction): [0.5, 1.5]
    assert_relative_eq!(bounds[[6, 0]], 0.5);
    assert_relative_eq!(bounds[[6, 1]], 1.5);

    // x8 (drainage time constant): [1, 100]
    assert_relative_eq!(bounds[[7, 0]], 1.0);
    assert_relative_eq!(bounds[[7, 1]], 100.0);
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
    let wrong_params = array![100.0, 0.5, 50.0, 3.0]; // Only 4 params instead of 8
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
fn test_pdm_nan_input() {
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
fn test_pdm_negative_precipitation() {
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
fn test_pdm_nan_pet() {
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
fn test_pdm_negative_pet() {
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
fn test_pdm_empty_arrays() {
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
fn test_pdm_params_outside_bounds() {
    // x1 way above upper bound (2000)
    let params = array![5000.0, 1.0, 0.5, 2.5, 1000.0, 15.0, 1.0, 50.0];
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
    // x1 is Cmax: higher Cmax → more soil storage → less runoff initially
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small = array![20.0, 1.0, 0.5, 2.5, 1000.0, 15.0, 1.0, 50.0];
    let params_large = array![1800.0, 1.0, 0.5, 2.5, 1000.0, 15.0, 1.0, 50.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x2_sensitivity() {
    // x2 is b (Pareto shape): higher b → more variable soil capacity → more saturation excess
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![1000.0, 0.05, 0.5, 2.5, 1000.0, 15.0, 1.0, 50.0];
    let params_high = array![1000.0, 1.8, 0.5, 2.5, 1000.0, 15.0, 1.0, 50.0];

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x7_sensitivity() {
    // x7 is rainfall correction: higher x7 → more effective precipitation → more streamflow
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![1000.0, 1.0, 0.5, 2.5, 1000.0, 15.0, 0.5, 50.0];
    let params_high = array![1000.0, 1.0, 0.5, 2.5, 1000.0, 15.0, 1.5, 50.0];

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));

    assert!(
        flow_high.sum() > flow_low.sum(),
        "Higher rainfall correction should produce more streamflow"
    );
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 10.0f64..2000.0,
        x2 in 0.01f64..2.0,
        x3 in 0.01f64..0.99,
        x4 in 0.5f64..5.0,
        x5 in 1.0f64..2000.0,
        x6 in 1.0f64..30.0,
        x7 in 0.5f64..1.5,
        x8 in 1.0f64..100.0
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
        x1 in 50.0f64..1500.0,
        x2 in 0.1f64..1.5,
        x3 in 0.05f64..0.9,
        x4 in 1.0f64..4.0,
        x5 in 10.0f64..1500.0,
        x6 in 2.0f64..25.0,
        x7 in 0.6f64..1.4,
        x8 in 2.0f64..80.0
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
fn test_wet_conditions_p_greater_than_e() {
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 5.0);

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
    let precip = Array1::from_elem(n, 1.0);
    let pet = Array1::from_elem(n, 10.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions without numerical issues"
    );
}

#[test]
fn test_saturation_excess_small_cmax() {
    // Small x1 (Cmax) with high precip forces saturation excess (ut1 > 0)
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![10.0, 0.5, 0.5, 2.5, 1000.0, 15.0, 1.0, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0, "Saturation excess should produce runoff");
}

#[test]
fn test_no_saturation_excess_large_cmax() {
    // Large x1 (Cmax) with low precip: no saturation excess
    let n = 50;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![2000.0, 0.5, 0.5, 2.5, 1000.0, 15.0, 1.0, 50.0];
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
fn test_delay_parameter_short() {
    // x4 at minimum (0.5)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1000.0, 1.0, 0.5, 0.5, 1000.0, 15.0, 1.0, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    // x4 at maximum (5.0)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1000.0, 1.0, 0.5, 5.0, 1000.0, 15.0, 1.0, 50.0];
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

    let params = array![1000.0, 1.0, 0.5, 2.0, 1000.0, 15.0, 1.0, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_threshold_drainage_below() {
    // x3 near max (0.99) means threshold = 0.99 * S_max — almost no drainage
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1000.0, 1.0, 0.99, 2.5, 1000.0, 15.0, 1.0, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_threshold_drainage_above() {
    // x3 near min (0.01) means threshold is very low — drainage kicks in easily
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1000.0, 1.0, 0.01, 2.5, 1000.0, 15.0, 1.0, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_cubic_ground_reservoir_extreme() {
    // x5 at minimum (1.0) — cubic reservoir empties fast
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![1000.0, 1.0, 0.5, 2.5, 1.0, 15.0, 1.0, 50.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x5 at maximum (2000.0) — cubic reservoir empties slowly
    let params_slow = array![1000.0, 1.0, 0.5, 2.5, 2000.0, 15.0, 1.0, 50.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_linear_cascade_extreme() {
    // x6 at minimum (1.0) — fast linear routing
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![1000.0, 1.0, 0.5, 2.5, 1000.0, 1.0, 1.0, 50.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x6 at maximum (30.0) — slow linear routing
    let params_slow = array![1000.0, 1.0, 0.5, 2.5, 1000.0, 30.0, 1.0, 50.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_drainage_time_constant_extreme() {
    // x8 at minimum (1.0) — very fast drainage
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![1000.0, 1.0, 0.5, 2.5, 1000.0, 15.0, 1.0, 1.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x8 at maximum (100.0) — very slow drainage
    let params_slow = array![1000.0, 1.0, 0.5, 2.5, 1000.0, 15.0, 1.0, 100.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_pareto_base_clamp() {
    // High b (x2) + high Cmax (x1) + heavy rain: stresses the Pareto inverse
    // where (1 - (b+1)*S/Cmax) could go negative without the .max(0.0) clamp
    let n = 200;
    let precip = Array1::from_elem(n, 80.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![100.0, 2.0, 0.5, 2.5, 1000.0, 15.0, 1.5, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Pareto base clamp should prevent NaN under heavy saturation"
    );
}

#[test]
fn test_high_precip_stress() {
    // Very high precipitation to stress all pathways
    let n = 100;
    let precip = Array1::from_elem(n, 100.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![50.0, 1.0, 0.5, 2.5, 500.0, 5.0, 1.5, 10.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle high precipitation stress"
    );
}

#[test]
fn test_evaporation_scaling() {
    // Test that evaporation factor works correctly: fill = (S/x1)*(x2+1)
    // With very small x2, fill ≈ S/x1, evap_factor ≈ 1 - (1-fill)^2
    let n = 100;
    let precip = Array1::from_elem(n, 5.0);
    let pet = Array1::from_elem(n, 10.0);

    let params = array![500.0, 0.01, 0.5, 2.5, 1000.0, 15.0, 1.0, 50.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_infiltration_excess() {
    // High rain on already-wetted soil: infiltration excess ut2 = pn - (S_new - S_old)
    // Use small Cmax and high precip
    let n = 50;
    let precip = Array1::from_elem(n, 30.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![20.0, 1.5, 0.5, 2.5, 500.0, 10.0, 1.0, 20.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0);
}
