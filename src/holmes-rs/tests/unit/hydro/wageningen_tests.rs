use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::wageningen::{
    init, param_descriptions, param_names, simulate,
};
use holmes_rs::hydro::HydroError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// =============================================================================
// Initialization
// =============================================================================

#[test]
fn test_init_bounds_shape() {
    let (defaults, bounds) = init();
    assert_eq!(
        defaults.len(),
        8,
        "WAGENINGEN model should have 8 parameters"
    );
    assert_eq!(bounds.shape(), &[8, 2]);
}

#[test]
fn test_init_bounds_ordered() {
    let (_, bounds) = init();
    for i in 0..bounds.nrows() {
        let lower = bounds[[i, 0]];
        let upper = bounds[[i, 1]];
        assert!(
            lower < upper,
            "Parameter {}: lower ({}) should be < upper ({})",
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
        assert!(default >= lower && default <= upper);
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
        assert!(!desc.is_empty());
    }
}

#[test]
fn test_init_specific_bounds() {
    let (_, bounds) = init();

    assert_relative_eq!(bounds[[0, 0]], 1.0);
    assert_relative_eq!(bounds[[0, 1]], 500.0);
    assert_relative_eq!(bounds[[1, 0]], 10.0);
    assert_relative_eq!(bounds[[1, 1]], 2000.0);
    assert_relative_eq!(bounds[[2, 0]], 0.1);
    assert_relative_eq!(bounds[[2, 1]], 1000.0);
    assert_relative_eq!(bounds[[3, 0]], 1.0);
    assert_relative_eq!(bounds[[3, 1]], 1000.0);
    assert_relative_eq!(bounds[[4, 0]], 0.1);
    assert_relative_eq!(bounds[[4, 1]], 500.0);
    assert_relative_eq!(bounds[[5, 0]], 0.5);
    assert_relative_eq!(bounds[[5, 1]], 50.0);
    assert_relative_eq!(bounds[[6, 0]], 1.0);
    assert_relative_eq!(bounds[[6, 1]], 50.0);
    assert_relative_eq!(bounds[[7, 0]], 0.5);
    assert_relative_eq!(bounds[[7, 1]], 5.0);
}

// =============================================================================
// Simulation
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
    assert!(streamflow.iter().all(|&q| q.is_finite()));
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
    assert!(streamflow.iter().all(|&q| q >= 0.0));
}

#[test]
fn test_simulate_output_length() {
    let (defaults, _) = init();

    for n in [10, 100, 365, 1000] {
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

        let streamflow =
            simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        assert_eq!(streamflow.len(), n);
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
// Error handling
// =============================================================================

#[test]
fn test_simulate_param_count_error() {
    let wrong_params = array![100.0, 500.0, 100.0, 100.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(8, 4))));
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
fn test_wageningen_nan_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, f64::NAN, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NonFiniteInput { .. })));
}

#[test]
fn test_wageningen_negative_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, -5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NegativeInput { .. })));
}

#[test]
fn test_wageningen_nan_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, f64::NAN, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NonFiniteInput { .. })));
}

#[test]
fn test_wageningen_negative_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, -1.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NegativeInput { .. })));
}

#[test]
fn test_wageningen_empty_arrays() {
    let (defaults, _) = init();
    let precip: Array1<f64> = array![];
    let pet: Array1<f64> = array![];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::EmptyInput { .. })));
}

#[test]
fn test_wageningen_params_outside_bounds() {
    // x1 way above upper bound
    let params = array![5000.0, 500.0, 100.0, 100.0, 50.0, 5.0, 10.0, 2.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParameterOutOfBounds { .. })));
}

// =============================================================================
// Branch coverage: production phase
// =============================================================================

#[test]
fn test_saturated_soil_branch() {
    // Small x1 + heavy rain forces S >= x1 every step (percolation branch)
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 0.5);
    // x1 small so S crosses threshold immediately; x2 moderate, x3 small so Is is non-trivial
    let params = array![5.0, 100.0, 10.0, 100.0, 50.0, 3.0, 5.0, 1.0];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0, "Saturated branch should yield flow");
}

#[test]
fn test_dry_soil_capillary_branch() {
    // Large x1, heavy PET, low rain forces S < x1 every step (capillary rise branch)
    let n = 100;
    let precip = Array1::from_elem(n, 0.1);
    let pet = Array1::from_elem(n, 15.0);
    // x1 large so S never reaches threshold; T=200 warm-start fuels capillary rise
    let params = array![400.0, 1000.0, 100.0, 100.0, 50.0, 3.0, 5.0, 1.0];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_full_pet_branch() {
    // S >= x1 → Es = E (full PET applied, no cosine reduction)
    let n = 50;
    let precip = Array1::from_elem(n, 30.0);
    let pet = Array1::from_elem(n, 4.0);
    let params = array![10.0, 200.0, 50.0, 100.0, 50.0, 3.0, 5.0, 1.0];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_reduced_pet_cosine_branch() {
    // S < x1 → Es = E · cos(pi/2 · (x1-S)/x1) (cosine-reduced ET)
    let n = 50;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 4.0);
    let params = array![400.0, 1000.0, 100.0, 100.0, 50.0, 3.0, 5.0, 1.0];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_soil_clamp_at_zero() {
    // Push S below zero before clamp: large ET, no rain, and warm-start S=30
    let n = 200;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 20.0);
    let (defaults, _) = init();

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Branch coverage: flow dissociation
// =============================================================================

#[test]
fn test_div_saturated_full_fast() {
    // T/x5 >= 1 ⇒ DIV = 1: all percolation goes to fast reservoir R
    // Start state T=200; x5 = 0.1 is the lower bound so T/x5 = 2000 >> 1.
    let n = 50;
    let precip = Array1::from_elem(n, 30.0);
    let pet = Array1::from_elem(n, 1.0);
    let params = array![5.0, 200.0, 20.0, 100.0, 0.1, 3.0, 5.0, 1.0];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_div_partial_mixed_routing() {
    // 0 < DIV < 1: x5 large so T/x5 = 200/500 = 0.4 → split flow
    let n = 50;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 2.0);
    let params = array![5.0, 200.0, 20.0, 100.0, 500.0, 3.0, 5.0, 1.0];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Delay parameter edge cases
// =============================================================================

#[test]
fn test_delay_parameter_short() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let params = array![100.0, 500.0, 100.0, 100.0, 50.0, 3.0, 5.0, 0.5];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let params = array![100.0, 500.0, 100.0, 100.0, 50.0, 3.0, 5.0, 5.0];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_integer() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let params = array![100.0, 500.0, 100.0, 100.0, 50.0, 3.0, 5.0, 2.0];

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Parameter sensitivity
// =============================================================================

#[test]
fn test_x1_sensitivity() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small = array![5.0, 500.0, 100.0, 100.0, 50.0, 3.0, 5.0, 1.0];
    let params_large = array![400.0, 500.0, 100.0, 100.0, 50.0, 3.0, 5.0, 1.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x6_fast_emptying_sensitivity() {
    // x6 controls fast reservoir emptying: smaller x6 → faster response
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![100.0, 500.0, 100.0, 100.0, 50.0, 0.5, 5.0, 1.0];
    let params_slow = array![100.0, 500.0, 100.0, 100.0, 50.0, 50.0, 5.0, 1.0];

    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x7_slow_emptying_sensitivity() {
    // x7 multiplies x6 for slow routing: larger x7 → slower baseflow
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_x7_low = array![100.0, 500.0, 100.0, 100.0, 50.0, 3.0, 1.0, 1.0];
    let params_x7_high =
        array![100.0, 500.0, 100.0, 100.0, 50.0, 3.0, 50.0, 1.0];

    let flow_low =
        simulate(params_x7_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_x7_high.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_low.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_high.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Wet / dry regime coverage
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
    assert!(streamflow.sum() > 0.0);
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

// =============================================================================
// Property tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 1.0f64..500.0,
        x2 in 10.0f64..2000.0,
        x3 in 0.1f64..1000.0,
        x4 in 1.0f64..1000.0,
        x5 in 0.1f64..500.0,
        x6 in 0.5f64..50.0,
        x7 in 1.0f64..50.0,
        x8 in 0.5f64..5.0,
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
        x1 in 10.0f64..400.0,
        x2 in 50.0f64..1500.0,
        x3 in 1.0f64..500.0,
        x4 in 10.0f64..500.0,
        x5 in 1.0f64..300.0,
        x6 in 1.0f64..20.0,
        x7 in 2.0f64..30.0,
        x8 in 1.0f64..4.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);
        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite()));
    }
}
