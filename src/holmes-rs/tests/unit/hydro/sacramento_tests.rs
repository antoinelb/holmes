use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::sacramento::{
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
    assert_eq!(
        defaults.len(),
        9,
        "SACRAMENTO model should have 9 parameters"
    );
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

    // x1 (direct routing reservoir capacity, d): [1, 20]
    assert_relative_eq!(bounds[[0, 0]], 1.0);
    assert_relative_eq!(bounds[[0, 1]], 20.0);

    // x2 (upper zone free-water capacity, mm): [30, 1000]
    assert_relative_eq!(bounds[[1, 0]], 30.0);
    assert_relative_eq!(bounds[[1, 1]], 1000.0);

    // x3 (lower zone emptying constant, d): [10, 500]
    assert_relative_eq!(bounds[[2, 0]], 10.0);
    assert_relative_eq!(bounds[[2, 1]], 500.0);

    // x4 (upper zone tension-water capacity, mm): [10, 500]
    assert_relative_eq!(bounds[[3, 0]], 10.0);
    assert_relative_eq!(bounds[[3, 1]], 500.0);

    // x5 (maximum percolation rate, mm/d): [0.01, 20]
    assert_relative_eq!(bounds[[4, 0]], 0.01);
    assert_relative_eq!(bounds[[4, 1]], 20.0);

    // x6 (hypodermic flow emptying constant, d): [1, 100]
    assert_relative_eq!(bounds[[5, 0]], 1.0);
    assert_relative_eq!(bounds[[5, 1]], 100.0);

    // x7 (upper zone partitioning coefficient): [0.01, 0.99]
    assert_relative_eq!(bounds[[6, 0]], 0.01);
    assert_relative_eq!(bounds[[6, 1]], 0.99);

    // x8 (deep percolation coefficient): [1, 50]
    assert_relative_eq!(bounds[[7, 0]], 1.0);
    assert_relative_eq!(bounds[[7, 1]], 50.0);

    // x9 (delay, d): [0.5, 10]
    assert_relative_eq!(bounds[[8, 0]], 0.5);
    assert_relative_eq!(bounds[[8, 1]], 10.0);
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
    let n = 200;
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

#[test]
fn test_simulate_mass_balance_sanity() {
    // Over a year of forcing, total Q should not exceed total P
    // (the residual goes to ET + storage change).
    let (defaults, _) = init();
    let n = 365;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();
    let total_q: f64 = streamflow.sum();
    let total_p: f64 = precip.sum();
    assert!(
        total_q <= total_p,
        "Total Q ({}) must not exceed total P ({})",
        total_q,
        total_p
    );
}

// =============================================================================
// Error Handling Tests
// =============================================================================

#[test]
fn test_simulate_param_count_error() {
    // 5 params instead of 9
    let wrong_params = array![10.0, 500.0, 250.0, 250.0, 10.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(9, 5))));
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
fn test_sacramento_nan_input() {
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
fn test_sacramento_negative_precipitation() {
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
fn test_sacramento_nan_pet() {
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
fn test_sacramento_negative_pet() {
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
fn test_sacramento_empty_arrays() {
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
fn test_sacramento_params_outside_bounds() {
    // x1 above upper bound (20)
    let params = array![100.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.5, 25.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject out-of-bounds parameters"
    );
}

#[test]
fn test_sacramento_params_below_bounds() {
    // x2 below lower bound (30)
    let params = array![10.0, 5.0, 250.0, 250.0, 10.0, 50.0, 0.5, 25.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::ParameterOutOfBounds { .. })),
        "Should reject parameters below lower bounds"
    );
}

// =============================================================================
// Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_x5_percolation_sensitivity() {
    // x5 is the max percolation rate. Higher x5 → more water routed through
    // the slow lower reservoir, lower direct flow from T's overflow.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 2.0, 1.0, 43);

    let params_slow = array![10.0, 500.0, 250.0, 250.0, 0.1, 50.0, 0.5, 25.0, 5.0];
    let params_fast = array![10.0, 500.0, 250.0, 250.0, 15.0, 50.0, 0.5, 25.0, 5.0];

    let flow_slow = simulate(params_slow.view(), precip.view(), pet.view()).unwrap();
    let flow_fast = simulate(params_fast.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_slow.iter().all(|&q| q.is_finite()));
    assert!(flow_fast.iter().all(|&q| q.is_finite()));
}

#[test]
fn test_x3_lower_emptying_sensitivity() {
    // x3 is the lower zone emptying constant (days). Larger x3 means
    // slower baseflow recession.
    let n = 365;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_short = array![10.0, 500.0, 10.0, 250.0, 10.0, 50.0, 0.5, 25.0, 5.0];
    let params_long = array![10.0, 500.0, 500.0, 250.0, 10.0, 50.0, 0.5, 25.0, 5.0];

    let flow_short = simulate(params_short.view(), precip.view(), pet.view()).unwrap();
    let flow_long = simulate(params_long.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_short.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_long.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x7_partitioning_extremes() {
    // x7 splits percolation It between L (lower routing) and R (free-water).
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // x7 = 0.01 (almost everything to R)
    let params_r_heavy = array![10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.01, 25.0, 5.0];
    let flow_r =
        simulate(params_r_heavy.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_r.iter().all(|&q| q.is_finite() && q >= 0.0));

    // x7 = 0.99 (almost everything to L)
    let params_l_heavy = array![10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.99, 25.0, 5.0];
    let flow_l =
        simulate(params_l_heavy.view(), precip.view(), pet.view()).unwrap();
    assert!(flow_l.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x8_deep_percolation_sensitivity() {
    // x8 damps Qr (higher x8 → less baseflow reaches the outlet).
    let n = 365;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params_low = array![10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.5, 1.0, 5.0];
    let params_high = array![10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.5, 50.0, 5.0];

    let flow_low = simulate(params_low.view(), precip.view(), pet.view()).unwrap();
    let flow_high = simulate(params_high.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_low.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_high.iter().all(|&q| q.is_finite() && q >= 0.0));

    // Stronger deep-percolation damping → less baseflow → smaller total Q
    assert!(
        flow_low.sum() > flow_high.sum(),
        "Lower x8 (weaker damping) should yield more total flow"
    );
}

// =============================================================================
// Branch Coverage Tests
// =============================================================================

#[test]
fn test_wet_conditions() {
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
fn test_dry_conditions() {
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 10.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_tension_overflow() {
    // Small x4 with high precipitation triggers Qt0 = max(0, T - x4)
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 2.0);

    let params = array![10.0, 500.0, 250.0, 10.0, 10.0, 50.0, 0.5, 25.0, 5.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(
        streamflow.sum() > 0.0,
        "Tension overflow should produce direct runoff"
    );
}

#[test]
fn test_l_goes_negative_triggers_ir_correction() {
    // The `if L<0` branch is the only place water moves "up" in the model:
    // it pulls Ir from R when residual PET over-evaporates L.
    // For L to go negative, el = e_deep * L / (XF1+XF2) must exceed L,
    // which requires e_deep > 33 mm/d. That's only reachable with large
    // PET forcing that passes through the tension store unused — so we
    // start with a wet pulse (to fill L), then immediately dry with very
    // high PET.
    let n = 80;
    let mut precip = Array1::zeros(n);
    for i in 0..5 {
        precip[i] = 30.0; // Wet pulse: fills T, percolates to L
    }
    let pet = Array1::from_elem(n, 60.0); // Huge PET drives el > L

    // x7 near 1 so almost all percolation is routed to L; x5 high so
    // percolation It is generous.
    let params =
        array![5.0, 100.0, 250.0, 50.0, 15.0, 50.0, 0.95, 5.0, 2.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_l_negative_with_no_r_free_space() {
    // Alternate branch: L goes negative but R is at or below (x2 - XF2)
    // so `(R - (x2-XF2)).max(0.0)` is 0 and the correction transfers
    // nothing — L just clamps at 0 and mass is lost. Still needs to be
    // covered to not regress.
    let n = 40;
    let mut precip = Array1::zeros(n);
    precip[0] = 50.0;
    precip[1] = 50.0;
    let pet = Array1::from_elem(n, 80.0);

    // Large x2 (=1000) means x2 - XF2 = 970; R (~ initial 100) is way
    // below that, so the free-space test yields 0.
    let params =
        array![5.0, 1000.0, 250.0, 50.0, 15.0, 50.0, 0.95, 5.0, 2.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_short() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.5, 25.0, 0.5];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.5, 25.0, 10.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_parameter_integer() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![10.0, 500.0, 250.0, 250.0, 10.0, 50.0, 0.5, 25.0, 3.0];
    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_all_param_corners() {
    // Iterate each parameter to its low and high bound with the others at
    // their default to exercise clamping, divisions, and branches at the
    // edges of the admissible domain.
    let (defaults, bounds) = init();
    let n = 80;
    let precip = helpers::generate_precipitation(n, 4.0, 0.25, 17);
    let pet = helpers::generate_pet(n, 2.5, 1.0, 19);

    for i in 0..9 {
        for &edge in &[bounds[[i, 0]], bounds[[i, 1]]] {
            let mut params = defaults.clone();
            params[i] = edge;
            let flow =
                simulate(params.view(), precip.view(), pet.view()).unwrap();
            assert!(
                flow.iter().all(|&q| q.is_finite() && q >= 0.0),
                "flow must stay finite and non-negative with x{} = {}",
                i + 1,
                edge
            );
        }
    }
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 1.0f64..20.0,
        x2 in 30.0f64..1000.0,
        x3 in 10.0f64..500.0,
        x4 in 10.0f64..500.0,
        x5 in 0.01f64..20.0,
        x6 in 1.0f64..100.0,
        x7 in 0.01f64..0.99,
        x8 in 1.0f64..50.0,
        x9 in 0.5f64..10.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8, x9];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q >= 0.0 && q.is_finite()));
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
    fn prop_mass_balance(
        x1 in 1.0f64..20.0,
        x2 in 30.0f64..1000.0,
        x3 in 10.0f64..500.0,
        x4 in 10.0f64..500.0,
        x5 in 0.01f64..20.0,
        x6 in 1.0f64..100.0,
        x7 in 0.01f64..0.99,
        x8 in 1.0f64..50.0,
        x9 in 0.5f64..10.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8, x9];
        let precip = helpers::generate_precipitation(120, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(120, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        // Over a full year the sum of Q must not exceed sum of P
        let total_q: f64 = streamflow.sum();
        let total_p: f64 = precip.sum();
        prop_assert!(total_q <= total_p + 1e-9);
    }
}
