use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::mordor::{
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
    assert_eq!(defaults.len(), 6, "MORDOR model should have 6 parameters");
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

    // x1 (rain correction coefficient): [0.5, 2.0]
    assert_relative_eq!(bounds[[0, 0]], 0.5);
    assert_relative_eq!(bounds[[0, 1]], 2.0);

    // x2 (emptying constant of L): [1, 1000]
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 1000.0);

    // x3 (emptying constant of N): [0.01, 100]
    assert_relative_eq!(bounds[[2, 0]], 0.01);
    assert_relative_eq!(bounds[[2, 1]], 100.0);

    // x4 (UH2 response time): [0.5, 10]
    assert_relative_eq!(bounds[[3, 0]], 0.5);
    assert_relative_eq!(bounds[[3, 1]], 10.0);

    // x5 (capacity of U): [1, 1000]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 1000.0);

    // x6 (capacity of L): [1, 1000]
    assert_relative_eq!(bounds[[5, 0]], 1.0);
    assert_relative_eq!(bounds[[5, 1]], 1000.0);
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
    let wrong_params = array![1.0, 500.0, 50.0, 5.0]; // Only 4 params instead of 6
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
fn test_mordor_nan_input() {
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
fn test_mordor_negative_precipitation() {
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
fn test_mordor_nan_pet() {
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
fn test_mordor_negative_pet() {
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
fn test_mordor_empty_arrays() {
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
fn test_mordor_params_outside_bounds() {
    // x1 above upper bound (2.0)
    let params = array![3.0, 500.0, 50.0, 5.0, 500.0, 500.0];
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
fn test_x1_rain_correction_sensitivity() {
    // x1 is a rain correction coefficient: Pl = P * x1
    // Higher x1 → more effective precipitation → more streamflow
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![0.6, 500.0, 50.0, 5.0, 500.0, 500.0];
    let params_high = array![1.8, 500.0, 50.0, 5.0, 500.0, 500.0];

    let flow_low =
        simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high =
        simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite()));
    assert!(flow_high.iter().all(|&q| q.is_finite()));
    assert!(
        flow_high.sum() > flow_low.sum(),
        "Higher rain correction should produce more streamflow"
    );
}

#[test]
fn test_x2_emptying_constant_sensitivity() {
    // x2 controls drainage from L: vl = L / x2
    // Higher x2 → slower drainage
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_fast = array![1.0, 10.0, 50.0, 5.0, 500.0, 500.0];
    let params_slow = array![1.0, 900.0, 50.0, 5.0, 500.0, 500.0];

    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_fast.iter().all(|&q| q.is_finite()));
    assert!(flow_slow.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x5_capacity_sensitivity() {
    // x5 is the capacity of surface reservoir U
    // Larger x5 → more storage before overflow → less immediate runoff
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small = array![1.0, 500.0, 50.0, 5.0, 5.0, 500.0];
    let params_large = array![1.0, 500.0, 50.0, 5.0, 900.0, 500.0];

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite()));
    assert!(flow_large.iter().all(|&q| q.is_finite()));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 0.5f64..2.0,
        x2 in 1.0f64..1000.0,
        x3 in 0.01f64..100.0,
        x4 in 0.5f64..10.0,
        x5 in 1.0f64..1000.0,
        x6 in 1.0f64..1000.0
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
        x1 in 0.7f64..1.5,
        x2 in 50.0f64..500.0,
        x3 in 1.0f64..50.0,
        x4 in 1.0f64..8.0,
        x5 in 50.0f64..500.0,
        x6 in 50.0f64..500.0
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
fn test_wet_conditions() {
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
    assert!(streamflow.sum() > 0.0, "Should produce flow in wet conditions");
}

#[test]
fn test_dry_conditions() {
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 10.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions"
    );
}

#[test]
fn test_soil_dries_to_zero() {
    let n = 200;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 20.0);

    let (defaults, _) = init();
    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle reservoir drying without numerical issues"
    );
}

#[test]
fn test_u_overflow() {
    // Small x5 with high precipitation forces overflow from U
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![1.5, 500.0, 50.0, 5.0, 5.0, 500.0]; // x5=5 (tiny U)
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0, "Overflow should produce runoff");
}

#[test]
fn test_no_u_overflow() {
    // Large x5 with low precipitation: U never overflows
    let n = 50;
    let precip = Array1::from_elem(n, 0.1);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![1.0, 500.0, 50.0, 5.0, 1000.0, 500.0]; // x5=1000 (huge)
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh2_short_time_base() {
    // x4 at minimum (0.5) — very short UH2
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1.0, 500.0, 50.0, 0.5, 500.0, 500.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh2_long_time_base() {
    // x4 at maximum (10.0) — long UH2
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1.0, 500.0, 50.0, 10.0, 500.0, 500.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh2_integer_time_base() {
    // x4 = 2.0 (exact integer) — tests edge case in UH2 construction
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![1.0, 500.0, 50.0, 2.0, 500.0, 500.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x3_nonlinear_drainage() {
    // x3 controls cubic drainage from N: vn = min(N, (N/x3)^3)
    // Small x3 → fast drainage, Large x3 → slow drainage
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // x3 near minimum
    let params_small = array![1.0, 500.0, 0.01, 5.0, 500.0, 500.0];
    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_small.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x3 near maximum
    let params_large = array![1.0, 500.0, 100.0, 5.0, 500.0, 500.0];
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_large.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_l_capacity_extremes() {
    // x6 controls L reservoir capacity — test at extremes
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_small = array![1.0, 500.0, 50.0, 5.0, 500.0, 1.0];
    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_small.iter().all(|&q| q.is_finite() && q >= 0.0));

    let params_large = array![1.0, 500.0, 50.0, 5.0, 500.0, 1000.0];
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_large.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_high_inflow_stress() {
    // Very high precipitation to stress all reservoirs
    let n = 100;
    let precip = Array1::from_elem(n, 100.0);
    let pet = Array1::from_elem(n, 1.0);

    let params = array![2.0, 1.0, 0.01, 0.5, 1.0, 1.0]; // small reservoirs, fast drainage
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle extreme inflow"
    );
}

#[test]
fn test_z_reservoir_saturation() {
    // Z is capped at 90mm — sustained wet conditions should saturate Z
    // causing all drainage to go to rapid underground runoff
    let n = 365;
    let precip = Array1::from_elem(n, 15.0);
    let pet = Array1::from_elem(n, 3.0);

    let params = array![1.0, 10.0, 50.0, 5.0, 50.0, 100.0]; // fast L drainage
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_rain_correction_extremes() {
    // x1 at bounds
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_min = array![0.5, 500.0, 50.0, 5.0, 500.0, 500.0];
    let flow_min =
        simulate(params_min.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_min.iter().all(|&q| q.is_finite() && q >= 0.0));

    let params_max = array![2.0, 500.0, 50.0, 5.0, 500.0, 500.0];
    let flow_max =
        simulate(params_max.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_max.iter().all(|&q| q.is_finite() && q >= 0.0));
}
