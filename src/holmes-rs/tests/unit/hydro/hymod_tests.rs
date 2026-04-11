use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::hymod::{
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
    assert_eq!(defaults.len(), 6, "HYMOD model should have 6 parameters");
    assert_eq!(
        bounds.shape(),
        &[6, 2],
        "Bounds should be 6x2 (params x [lower, upper])"
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
    assert_eq!(param_names.len(), 6);
    assert_eq!(param_names, &["x1", "x2", "x3", "x4", "x5", "x6"]);
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

    // x1 (Cmax — maximum soil capacity): [1, 1500]
    assert_relative_eq!(bounds[[0, 0]], 1.0);
    assert_relative_eq!(bounds[[0, 1]], 1500.0);

    // x2 (Bexp — Pareto shape): [0.1, 2.0]
    assert_relative_eq!(bounds[[1, 0]], 0.1);
    assert_relative_eq!(bounds[[1, 1]], 2.0);

    // x3 (alpha — fast/slow split fraction): [0.01, 0.99]
    assert_relative_eq!(bounds[[2, 0]], 0.01);
    assert_relative_eq!(bounds[[2, 1]], 0.99);

    // x4 (Delay — unit hydrograph length, days): [0.1, 5.0]
    assert_relative_eq!(bounds[[3, 0]], 0.1);
    assert_relative_eq!(bounds[[3, 1]], 5.0);

    // x5 (Rs — slow residence scaler): [1, 1000]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 1000.0);

    // x6 (Rq — fast residence time, days): [1, 10]
    assert_relative_eq!(bounds[[5, 0]], 1.0);
    assert_relative_eq!(bounds[[5, 1]], 10.0);
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
    // Only 4 params instead of 6
    let wrong_params = array![100.0, 0.5, 50.0, 3.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(6, 4))));
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
fn test_hymod_nan_input() {
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
fn test_hymod_nan_pet() {
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
fn test_hymod_negative_precipitation() {
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
fn test_hymod_negative_pet() {
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
fn test_hymod_empty_arrays() {
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
fn test_hymod_params_outside_bounds() {
    // x1 way above upper bound (1500)
    let params = array![5000.0, 1.0, 0.5, 2.5, 500.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject out-of-bounds parameters"
    );
}

#[test]
fn test_hymod_x2_below_bound() {
    // x2 = 0 (below lower bound 0.1)
    let params = array![500.0, 0.0, 0.5, 2.5, 500.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { .. })
    ));
}

#[test]
fn test_hymod_x6_below_bound() {
    // x6 = 0.5 (below lower bound 1.0)
    let params = array![500.0, 1.0, 0.5, 2.5, 500.0, 0.5];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { .. })
    ));
}

// =============================================================================
// Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_x1_sensitivity() {
    // x1 is the max soil moisture capacity: larger = more storage = less runoff
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small = array![10.0, 1.0, 0.5, 2.5, 500.0, 5.0];
    let params_large = array![1400.0, 1.0, 0.5, 2.5, 500.0, 5.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));

    // Larger Cmax absorbs more rain => less total streamflow
    assert!(
        flow_small.sum() > flow_large.sum(),
        "Smaller Cmax should produce more streamflow"
    );
}

#[test]
fn test_x3_sensitivity() {
    // x3 splits excess between fast (3 linear reservoirs) and slow (ground).
    // Very high x3 sends almost everything to the fast path — same water,
    // just routed differently; both must stay finite and non-negative.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_slow = array![500.0, 1.0, 0.05, 2.5, 500.0, 5.0]; // mostly slow
    let params_fast = array![500.0, 1.0, 0.95, 2.5, 500.0, 5.0]; // mostly fast

    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x6_residence_time_sensitivity() {
    // Very small x6 (fast reservoirs drain almost every step) vs very large x6
    // (reservoirs barely drain). Both must stay stable.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_quick = array![500.0, 1.0, 0.5, 2.5, 500.0, 1.0];
    let params_slow = array![500.0, 1.0, 0.5, 2.5, 500.0, 10.0];

    let flow_quick =
        simulate(params_quick.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_quick.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 1.0f64..1500.0,
        x2 in 0.1f64..2.0,
        x3 in 0.01f64..0.99,
        x4 in 0.1f64..5.0,
        x5 in 1.0f64..1000.0,
        x6 in 1.0f64..10.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6];
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
        x2 in 0.2f64..1.8,
        x3 in 0.1f64..0.9,
        x4 in 0.5f64..4.0,
        x5 in 5.0f64..500.0,
        x6 in 1.5f64..8.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6];
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

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions without numerical issues"
    );
}

#[test]
fn test_saturation_excess_overflow() {
    // Tiny Cmax + huge precipitation: forces Ut1 > 0 (saturation excess branch).
    let n = 100;
    let precip = Array1::from_elem(n, 100.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![2.0, 1.0, 0.5, 2.5, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0);
}

#[test]
fn test_no_saturation_excess() {
    // Huge Cmax + tiny precip: S never exceeds Cmax, Ut1 stays 0.
    let n = 50;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![1500.0, 1.0, 0.5, 2.5, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_soil_dries_to_zero() {
    // Heavy ET, no precip — soil should clamp at 0 via .max(0.0)
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
    // x4 at minimum (0.1) — near-zero delay
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 1.0, 0.5, 0.1, 500.0, 5.0];
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

    let params = array![500.0, 1.0, 0.5, 5.0, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_integer() {
    // x4 = 2.0 (exact integer) — tests ceil() edge case in delay vector setup
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 1.0, 0.5, 2.0, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_pareto_shape_extreme_low() {
    // x2 at minimum (0.1) — near-linear soil distribution
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 0.1, 0.5, 2.5, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_pareto_shape_extreme_high() {
    // x2 at maximum (2.0) — strongly concave soil distribution (fast saturation)
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 2.0, 0.5, 2.5, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_alpha_all_fast() {
    // x3 at maximum: ~all excess to fast cascade, slow reservoir starved
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 1.0, 0.99, 2.5, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_alpha_all_slow() {
    // x3 at minimum: ~all non-saturation excess to the slow reservoir
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![500.0, 1.0, 0.01, 2.5, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_slow_reservoir_extreme_scaler() {
    // x5 at maximum (1000): extremely slow groundwater drainage
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_slow = array![500.0, 1.0, 0.5, 2.5, 1000.0, 5.0];
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x5 at minimum (1): slow reservoir drains as fast as the fast one
    let params_fast = array![500.0, 1.0, 0.5, 2.5, 1.0, 5.0];
    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_high_pareto_with_small_cmax_initialization_clamp() {
    // Stress the init_state S-clamp: very high x2 (2.0) means
    // x1/(x2+1) = x1/3 < 0.2*x1, so the clamp must kick in.
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1.0, 2.0, 0.5, 2.5, 500.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Initialization clamp must prevent NaN when x2 is at upper bound"
    );
}
