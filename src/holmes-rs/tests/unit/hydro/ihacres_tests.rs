use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::ihacres::{
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
    assert_eq!(defaults.len(), 7, "IHACRES model should have 7 parameters");
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
    assert_eq!(param_names, &["x1", "x2", "x3", "x4", "x5", "x6", "x7"]);
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

    // x1 (forcing 1/C): [1, 1000]
    assert_relative_eq!(bounds[[0, 0]], 1.0);
    assert_relative_eq!(bounds[[0, 1]], 1000.0);

    // x2 (fast-flow fraction): [0.01, 0.99]
    assert_relative_eq!(bounds[[1, 0]], 0.01);
    assert_relative_eq!(bounds[[1, 1]], 0.99);

    // x3 (fast routing time constant): [1.0, 100] — stability constraint
    assert_relative_eq!(bounds[[2, 0]], 1.0);
    assert_relative_eq!(bounds[[2, 1]], 100.0);

    // x4 (slow multiplier): [1, 1000]
    assert_relative_eq!(bounds[[3, 0]], 1.0);
    assert_relative_eq!(bounds[[3, 1]], 1000.0);

    // x5 (delay): [0.5, 5]
    assert_relative_eq!(bounds[[4, 0]], 0.5);
    assert_relative_eq!(bounds[[4, 1]], 5.0);

    // x6 (PET modulation f): [0.1, 10]
    assert_relative_eq!(bounds[[5, 0]], 0.1);
    assert_relative_eq!(bounds[[5, 1]], 10.0);

    // x7 (drying constant Tw): [0.1, 10]
    assert_relative_eq!(bounds[[6, 0]], 0.1);
    assert_relative_eq!(bounds[[6, 1]], 10.0);
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

    // With no precipitation, the routing reservoirs decay from initial states
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
fn test_ihacres_nan_input() {
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
fn test_ihacres_negative_precipitation() {
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
fn test_ihacres_nan_pet() {
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
fn test_ihacres_negative_pet() {
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
fn test_ihacres_empty_arrays() {
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
fn test_ihacres_x1_above_bounds() {
    // x1 way above upper bound (1000)
    let params = array![5000.0, 0.5, 50.0, 500.0, 2.5, 5.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject x1 above upper bound"
    );
}

#[test]
fn test_ihacres_x2_below_bounds() {
    // x2 below lower bound (0.01)
    let params = array![500.0, 0.0, 50.0, 500.0, 2.5, 5.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject x2 below lower bound"
    );
}

#[test]
fn test_ihacres_x3_below_bounds() {
    // x3 below lower bound (1.0) — explicit-Euler instability region
    let params = array![500.0, 0.5, 0.5, 500.0, 2.5, 5.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject x3 below lower bound"
    );
}

#[test]
fn test_ihacres_x4_below_bounds() {
    // x4 below 1.0 (slow store would become faster than fast — nonsense)
    let params = array![500.0, 0.5, 50.0, 0.5, 2.5, 5.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject x4 below 1.0"
    );
}

#[test]
fn test_ihacres_x5_below_bounds() {
    // x5 below 0.5 (delay vector construction would underflow)
    let params = array![500.0, 0.5, 50.0, 500.0, 0.1, 5.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject x5 below 0.5"
    );
}

#[test]
fn test_ihacres_x6_below_bounds() {
    // x6 below 0.1
    let params = array![500.0, 0.5, 50.0, 500.0, 2.5, 0.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject x6 below 0.1"
    );
}

#[test]
fn test_ihacres_x7_above_bounds() {
    // x7 above upper bound (10)
    let params = array![500.0, 0.5, 50.0, 500.0, 2.5, 5.0, 50.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject x7 above upper bound"
    );
}

// =============================================================================
// Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_x1_mass_balance_scaling() {
    // x1 = 1/C, the mass-balance forcing scaler.
    // Smaller x1 → larger P/x1 → moisture index grows faster → larger
    // effective rainfall → more total streamflow.
    let n = 365;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // Same params except x1
    let params_small = array![10.0, 0.5, 50.0, 500.0, 2.5, 5.0, 5.0];
    let params_large = array![1000.0, 0.5, 50.0, 500.0, 2.5, 5.0, 5.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_large.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(
        flow_small.sum() > flow_large.sum(),
        "Smaller x1 (larger 1/C scaler) should produce more streamflow"
    );
}

#[test]
fn test_x2_flow_split_extremes() {
    // x2 = fast-flow fraction. Extremes test branch coverage on the split.
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // Mostly fast routing
    let params_fast = array![500.0, 0.95, 50.0, 500.0, 2.5, 5.0, 5.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));

    // Mostly slow routing
    let params_slow = array![500.0, 0.05, 50.0, 500.0, 2.5, 5.0, 5.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x3_x4_routing_constants() {
    // x3 controls fast time constant; x3*x4 controls slow.
    // Faster fast emptying → more peaked response.
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![500.0, 0.5, 1.0, 10.0, 2.5, 5.0, 5.0];
    let params_slow = array![500.0, 0.5, 100.0, 1000.0, 2.5, 5.0, 5.0];

    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x6_x7_drying_extremes() {
    // x6 (PET modulation) and x7 (Tw drying) jointly control El.
    // Big x7 with small x6/E → wetness persists; opposite → wetness decays.
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // Persistent moisture (high Tw, low PET sensitivity)
    let params_persist = array![500.0, 0.5, 50.0, 500.0, 2.5, 10.0, 10.0];
    let flow_persist =
        simulate(params_persist.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_persist.iter().all(|&q| q.is_finite() && q >= 0.0));

    // Rapid drying (low Tw, high PET sensitivity)
    let params_dry = array![500.0, 0.5, 50.0, 500.0, 2.5, 0.1, 0.1];
    let flow_dry =
        simulate(params_dry.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_dry.iter().all(|&q| q.is_finite() && q >= 0.0));
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
fn test_drying_clamp_engaged() {
    // E/x6 > x7 forces El = max(0, x7 - E/x6) to clamp at zero.
    // With El = 0, exp(El) = 1, so the wetness reset path is exercised.
    let n = 100;
    let precip = Array1::from_elem(n, 5.0);
    let pet = Array1::from_elem(n, 50.0); // E/x6 = 50/0.5 = 100 >> x7

    // x6 small + x7 small → El clamps to zero immediately
    let params = array![500.0, 0.5, 50.0, 500.0, 2.5, 0.5, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_drying_clamp_unengaged() {
    // E small → E/x6 small → x7 - E/x6 stays positive → El > 0
    let n = 100;
    let precip = Array1::from_elem(n, 5.0);
    let pet = Array1::from_elem(n, 0.1); // Tiny PET

    let params = array![500.0, 0.5, 50.0, 500.0, 2.5, 10.0, 10.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_short() {
    // x5 at minimum (0.5) — short delay
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 0.5, 50.0, 500.0, 0.5, 5.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    // x5 at maximum (5.0) — long delay
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 0.5, 50.0, 500.0, 5.0, 5.0, 5.0];
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

    let params = array![500.0, 0.5, 50.0, 500.0, 2.0, 5.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_fractional() {
    // x5 = 2.5 — fractional delay, exercises the two-tap distribution
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 0.5, 50.0, 500.0, 2.5, 5.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_pet_zero_throughout() {
    // PET = 0 forces El = max(0, x7 - 0) = x7 (drying still happens via Tw alone)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = Array1::zeros(n);

    let (defaults, _) = init();
    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_constant_steady_input() {
    // Constant rainfall and PET — exercises the slow recursion path.
    let n = 200;
    let precip = Array1::from_elem(n, 3.0);
    let pet = Array1::from_elem(n, 1.0);

    let (defaults, _) = init();
    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(
        streamflow.sum() > 0.0,
        "Constant forcing should produce positive flow"
    );
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 1.0f64..1000.0,
        x2 in 0.01f64..0.99,
        x3 in 1.0f64..100.0,
        x4 in 1.0f64..1000.0,
        x5 in 0.5f64..5.0,
        x6 in 0.1f64..10.0,
        x7 in 0.1f64..10.0,
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
        x1 in 50.0f64..500.0,
        x2 in 0.1f64..0.9,
        x3 in 1.0f64..50.0,
        x4 in 5.0f64..500.0,
        x5 in 1.0f64..4.0,
        x6 in 0.5f64..5.0,
        x7 in 0.5f64..5.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite()));
    }
}
