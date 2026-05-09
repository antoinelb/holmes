use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::smar::{
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
    assert_eq!(defaults.len(), 8, "SMAR model should have 8 parameters");
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

    // x1 (direct flow coefficient): [0.01, 1.0]
    assert_relative_eq!(bounds[[0, 0]], 0.01);
    assert_relative_eq!(bounds[[0, 1]], 1.0);

    // x2 (infiltration parameter): [0.01, 10.0]
    assert_relative_eq!(bounds[[1, 0]], 0.01);
    assert_relative_eq!(bounds[[1, 1]], 10.0);

    // x3 (PET reduction coefficient): [0.01, 0.99]
    assert_relative_eq!(bounds[[2, 0]], 0.01);
    assert_relative_eq!(bounds[[2, 1]], 0.99);

    // x4 (quadratic routing capacity): [1.0, 500.0]
    assert_relative_eq!(bounds[[3, 0]], 1.0);
    assert_relative_eq!(bounds[[3, 1]], 500.0);

    // x5 (linear routing constant): [1.0, 200.0]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 200.0);

    // x6 (delay): [0.5, 5.0]
    assert_relative_eq!(bounds[[5, 0]], 0.5);
    assert_relative_eq!(bounds[[5, 1]], 5.0);

    // x7 (PET correction): [0.1, 2.0]
    assert_relative_eq!(bounds[[6, 0]], 0.1);
    assert_relative_eq!(bounds[[6, 1]], 2.0);

    // x8 (partitioning coefficient): [0.01, 0.99]
    assert_relative_eq!(bounds[[7, 0]], 0.01);
    assert_relative_eq!(bounds[[7, 1]], 0.99);
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
    let wrong_params = array![0.5, 5.0, 0.5, 250.0]; // Only 4 params
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
fn test_smar_nan_input() {
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
fn test_smar_negative_precipitation() {
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
fn test_smar_nan_pet() {
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
fn test_smar_negative_pet() {
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
fn test_smar_empty_arrays() {
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
fn test_smar_params_outside_bounds() {
    // x1 above upper bound (1.0)
    let params = array![5.0, 5.0, 0.5, 250.0, 100.0, 2.5, 1.0, 0.5];
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
    // x1 controls direct runoff fraction: Pr1 = H' * Pn
    // Higher x1 means more direct flow, less infiltration
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![0.05, 5.0, 0.5, 250.0, 100.0, 2.5, 1.0, 0.5];
    let params_high = array![0.95, 5.0, 0.5, 250.0, 100.0, 2.5, 1.0, 0.5];

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x2_sensitivity() {
    // x2 controls infiltration capacity: Fr = Ym·exp(-x2·S/125)
    // Higher x2 means less infiltration
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![0.5, 0.1, 0.5, 250.0, 100.0, 2.5, 1.0, 0.5];
    let params_high = array![0.5, 9.0, 0.5, 250.0, 100.0, 2.5, 1.0, 0.5];

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x7_sensitivity() {
    // x7 is PET correction: E_corr = x7 · E
    // Higher x7 means more ET → less streamflow
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low_et = array![0.5, 5.0, 0.5, 250.0, 100.0, 2.5, 0.2, 0.5];
    let params_high_et = array![0.5, 5.0, 0.5, 250.0, 100.0, 2.5, 1.8, 0.5];

    let flow_low_et =
        simulate(params_low_et.view(), precip.view(), pet.view()).unwrap();
    let flow_high_et =
        simulate(params_high_et.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low_et.iter().all(|&q| q.is_finite()));
    assert!(flow_high_et.iter().all(|&q| q.is_finite()));

    assert!(
        flow_low_et.sum() > flow_high_et.sum(),
        "Lower PET correction should produce more streamflow"
    );
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 0.01f64..1.0,
        x2 in 0.01f64..10.0,
        x3 in 0.01f64..0.99,
        x4 in 1.0f64..500.0,
        x5 in 1.0f64..200.0,
        x6 in 0.5f64..5.0,
        x7 in 0.1f64..2.0,
        x8 in 0.01f64..0.99
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
        x1 in 0.1f64..0.9,
        x2 in 1.0f64..8.0,
        x3 in 0.1f64..0.9,
        x4 in 10.0f64..400.0,
        x5 in 5.0f64..150.0,
        x6 in 1.0f64..4.0,
        x7 in 0.3f64..1.5,
        x8 in 0.1f64..0.9
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
fn test_soil_layers_saturate() {
    // High precipitation fills all 16 layers, producing interflow
    let n = 200;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![0.1, 0.5, 0.5, 250.0, 100.0, 2.5, 0.5, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(
        streamflow.sum() > 0.0,
        "Saturated soil should produce runoff"
    );
}

#[test]
fn test_soil_dries_to_zero() {
    // No precipitation + heavy ET drains all soil layers
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
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.5, 5.0, 0.5, 250.0, 100.0, 0.5, 1.0, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.5, 5.0, 0.5, 250.0, 100.0, 5.0, 1.0, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_integer() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.5, 5.0, 0.5, 250.0, 100.0, 2.0, 1.0, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x3_et_reduction_extremes() {
    // x3 near minimum (0.01) — ET drops very fast with depth
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![0.5, 5.0, 0.01, 250.0, 100.0, 2.5, 1.0, 0.5];
    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_low.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x3 near maximum (0.99) — ET stays high even in deep layers
    let params_high = array![0.5, 5.0, 0.99, 250.0, 100.0, 2.5, 1.0, 0.5];
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_high.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x8_partitioning_extremes() {
    // x8 near 0 — almost all interflow to linear reservoir
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_linear = array![0.5, 5.0, 0.5, 250.0, 100.0, 2.5, 1.0, 0.01];
    let flow_linear =
        simulate(params_linear.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_linear.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x8 near 1 — almost all interflow to quadratic reservoir
    let params_quad = array![0.5, 5.0, 0.5, 250.0, 100.0, 2.5, 1.0, 0.99];
    let flow_quad =
        simulate(params_quad.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_quad.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_quadratic_reservoir_high_inflow() {
    // Heavy precipitation forces large flows through the quadratic reservoir
    let n = 100;
    let precip = Array1::from_elem(n, 100.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![0.5, 0.5, 0.5, 10.0, 100.0, 2.5, 0.5, 0.9];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle high quadratic reservoir inflow"
    );
}

#[test]
fn test_linear_reservoir_slow_recession() {
    // Large x5 means very slow linear reservoir emptying
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![0.5, 5.0, 0.5, 250.0, 200.0, 2.5, 1.0, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_pet_correction_extremes() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // x7 = 0.1 (minimal PET correction)
    let params_low = array![0.5, 5.0, 0.5, 250.0, 100.0, 2.5, 0.1, 0.5];
    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_low.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x7 = 2.0 (maximum PET correction)
    let params_high = array![0.5, 5.0, 0.5, 250.0, 100.0, 2.5, 2.0, 0.5];
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_high.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_high_direct_flow() {
    // x1 at maximum with high precipitation — most rain becomes direct flow
    let n = 100;
    let precip = Array1::from_elem(n, 40.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![1.0, 5.0, 0.5, 250.0, 100.0, 2.5, 0.5, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle maximum direct flow coefficient"
    );
    assert!(streamflow.sum() > 0.0, "Should produce flow");
}

#[test]
fn test_all_bounds_corners() {
    // Test with all parameters at their lower bounds
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_min =
        array![0.01, 0.01, 0.01, 1.0, 1.0, 0.5, 0.1, 0.01];
    let flow_min =
        simulate(params_min.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_min.iter().all(|&q| q.is_finite() && q >= 0.0));

    // Test with all parameters at their upper bounds
    let params_max =
        array![1.0, 10.0, 0.99, 500.0, 200.0, 5.0, 2.0, 0.99];
    let flow_max =
        simulate(params_max.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_max.iter().all(|&q| q.is_finite() && q >= 0.0));
}
