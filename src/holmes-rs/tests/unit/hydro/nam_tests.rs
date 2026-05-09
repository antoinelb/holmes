use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::nam::{init, param_descriptions, param_names, simulate};
use holmes_rs::hydro::HydroError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// Default parameter set used as a starting point in many of the
// branch-coverage tests below. Mid-range values, taken from `init()`,
// keep every reservoir well within its bounds.
fn default_params() -> Array1<f64> {
    init().0
}

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_init_bounds_shape() {
    let (defaults, bounds) = init();
    assert_eq!(defaults.len(), 10, "NAM model should have 10 parameters");
    assert_eq!(
        bounds.shape(),
        &[10, 2],
        "Bounds should be 10x2 (params x [lower, upper])"
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
    assert_eq!(param_names.len(), 10);
    assert_eq!(
        param_names,
        &["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9", "x10"]
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

    // x1 (ground reservoir threshold, mm)
    assert_relative_eq!(bounds[[0, 0]], 1.0);
    assert_relative_eq!(bounds[[0, 1]], 1000.0);

    // x2 (routing reservoir emptying constant, d)
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 100.0);

    // x3 (sub-surface flow constant)
    assert_relative_eq!(bounds[[2, 0]], 1.0);
    assert_relative_eq!(bounds[[2, 1]], 100.0);

    // x4 (delay, d)
    assert_relative_eq!(bounds[[3, 0]], 0.5);
    assert_relative_eq!(bounds[[3, 1]], 10.0);

    // x5 (percolation constant) — strictly < 1
    assert_relative_eq!(bounds[[4, 0]], 0.01);
    assert_relative_eq!(bounds[[4, 1]], 0.99);

    // x6 (ground reservoir emptying constant, d)
    assert_relative_eq!(bounds[[5, 0]], 1.0);
    assert_relative_eq!(bounds[[5, 1]], 500.0);

    // x7 (soil reservoir capacity, mm)
    assert_relative_eq!(bounds[[6, 0]], 1.0);
    assert_relative_eq!(bounds[[6, 1]], 1000.0);

    // x8 (surface flow constant)
    assert_relative_eq!(bounds[[7, 0]], 1.0);
    assert_relative_eq!(bounds[[7, 1]], 100.0);

    // x9 (surface reservoir capacity, mm)
    assert_relative_eq!(bounds[[8, 0]], 1.0);
    assert_relative_eq!(bounds[[8, 1]], 1000.0);

    // x10 (capillary rise, mm)
    assert_relative_eq!(bounds[[9, 0]], 0.01);
    assert_relative_eq!(bounds[[9, 1]], 10.0);
}

// =============================================================================
// Simulation Tests
// =============================================================================

#[test]
fn test_simulate_basic() {
    let defaults = default_params();
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
    let defaults = default_params();
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
    let defaults = default_params();

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
    let defaults = default_params();
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
    // Only 4 params instead of 10
    let wrong_params = array![100.0, 50.0, 50.0, 3.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(10, 4))));
}

#[test]
fn test_simulate_length_mismatch() {
    let defaults = default_params();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0]; // Length mismatch

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::LengthMismatch(3, 2))));
}

#[test]
fn test_nam_nan_input() {
    let defaults = default_params();
    let precip = array![10.0, f64::NAN, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NonFiniteInput { .. })),
        "Should reject NaN in precipitation"
    );
}

#[test]
fn test_nam_negative_precipitation() {
    let defaults = default_params();
    let precip = array![10.0, -5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NegativeInput { .. })),
        "Should reject negative precipitation"
    );
}

#[test]
fn test_nam_nan_pet() {
    let defaults = default_params();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, f64::NAN, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NonFiniteInput { .. })),
        "Should reject NaN in PET"
    );
}

#[test]
fn test_nam_negative_pet() {
    let defaults = default_params();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, -1.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NegativeInput { .. })),
        "Should reject negative PET"
    );
}

#[test]
fn test_nam_empty_arrays() {
    let defaults = default_params();
    let precip: Array1<f64> = array![];
    let pet: Array1<f64> = array![];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::EmptyInput { .. })),
        "Should reject empty input arrays"
    );
}

#[test]
fn test_nam_x1_above_bounds() {
    let mut params = default_params();
    params[0] = 5000.0; // x1 max is 1000
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x1", .. })
    ));
}

#[test]
fn test_nam_x5_above_bounds() {
    // x5 has the unusual upper bound of 0.99 — exceeding it would
    // make the percolation denominator (1 - x5) collapse toward 0.
    let mut params = default_params();
    params[4] = 1.5;
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x5", .. })
    ));
}

#[test]
fn test_nam_x10_below_bounds() {
    let mut params = default_params();
    params[9] = -0.1; // x10 lower bound is 0.01
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x10", .. })
    ));
}

// =============================================================================
// Branch Coverage Tests — production phase
// =============================================================================

#[test]
fn test_wet_conditions_force_surface_overflow() {
    // High P, low E forces U > x9 -> overflow branch (PN > 0).
    // This is the only branch that exercises the entire production
    // block (QOF, G, DL0, overland cascade, soil recharge).
    let n = 100;
    let precip = Array1::from_elem(n, 30.0);
    let pet = Array1::from_elem(n, 1.0);

    // Small surface capacity x9 -> guaranteed overflow every step.
    let mut params = default_params();
    params[8] = 5.0;

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(
        streamflow.sum() > 0.0,
        "Overflow branch should produce positive flow"
    );
}

#[test]
fn test_dry_conditions_force_surface_emptied() {
    // Low P, high E forces U < 0 -> "emptied" branch (E1 > 0, PN = 0).
    // The residual demand E1 is then drawn from the soil store.
    let n = 100;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 15.0);

    // Small surface capacity so the surface store empties fast.
    let mut params = default_params();
    params[8] = 10.0;

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions and surface emptying"
    );
}

#[test]
fn test_surface_within_capacity() {
    // Moderate P, moderate E so 0 <= U <= x9 most of the time.
    // Hits the first arm of the if-else (E1 = 0, PN = 0).
    let n = 100;
    let precip = Array1::from_elem(n, 2.0);
    let pet = Array1::from_elem(n, 2.0);

    let streamflow =
        simulate(default_params().view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_groundwater_recharge_active() {
    // L/x7 > x5 + heavy spill -> the G branch fires.
    // Soil starts at x7/2 = 500 (with default x7=500.5), so a tiny x5
    // makes L/x7 > x5 immediately and recharge is non-zero from the
    // very first overflow.
    let n = 50;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 0.5);

    let mut params = default_params();
    params[4] = 0.05; // x5 very small -> recharge always active
    params[8] = 10.0; // x9 small -> guaranteed overflow

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_groundwater_recharge_inactive() {
    // L/x7 <= x5 + spill -> recharge stays at zero.
    // Drain L first via heavy ET, then dump rain.
    let n = 200;
    let mut precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 20.0);
    for i in (n / 2)..n {
        precip[i] = 30.0;
    }

    let mut params = default_params();
    params[4] = 0.95; // x5 near upper bound -> hard to exceed L/x7
    params[8] = 10.0;

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_dl0_exceeds_soil_capacity() {
    // PN huge, x7 tiny -> DL0 > x7 branch fires, forcing surplus
    // into G via DL1 and exercising the L > x7 clamp downstream.
    let n = 50;
    let precip = Array1::from_elem(n, 200.0);
    let pet = Array1::from_elem(n, 1.0);

    let mut params = default_params();
    params[6] = 5.0; // x7 (soil capacity) tiny
    params[8] = 5.0; // x9 (surface capacity) tiny -> all rain spills

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0);
}

// =============================================================================
// Branch Coverage Tests — groundwater + capillary rise
// =============================================================================

#[test]
fn test_baseflow_threshold_crossed() {
    // Sustained recharge drives gw below x1 -> baseflow active.
    // This is the GW <= x1 arm of the BF if-else.
    let n = 200;
    let precip = Array1::from_elem(n, 25.0);
    let pet = Array1::from_elem(n, 0.5);

    let mut params = default_params();
    params[0] = 80.0; // x1 (threshold) high so gw - G stays below it
    params[4] = 0.05; // x5 small -> lots of recharge
    params[8] = 5.0; // x9 small -> guaranteed overflow

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0, "Baseflow should produce flow");
}

#[test]
fn test_baseflow_threshold_not_reached() {
    // No precipitation: gw stays at its initial 50, no recharge,
    // and a high x1 means gw < x1 so... wait — that still triggers
    // the BF arm. To NOT trigger BF, we need gw > x1, which means
    // we need x1 < 50 (since initial gw = 50 with no recharge).
    let n = 50;
    let precip = Array1::zeros(n);
    let pet = Array1::zeros(n);

    let mut params = default_params();
    params[0] = 5.0; // x1 < initial gw -> no baseflow

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_bf1_emergency_branch() {
    // Force gw negative after BF: heavy continuous recharge with a
    // high x1 threshold and small x6 (fast ground reservoir
    // emptying) drives gw below zero and trips the BF1 reset.
    let n = 100;
    let precip = Array1::from_elem(n, 100.0);
    let pet = Array1::from_elem(n, 0.0);

    let mut params = default_params();
    params[0] = 999.0; // x1 huge -> BF formula returns large value
    params[4] = 0.05; // x5 tiny -> max recharge
    params[5] = 1.0; // x6 = 1 -> BF = (x1 - gw)/1 = x1 - gw, full deficit closed
    params[8] = 5.0; // x9 small -> guaranteed overflow

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_capillary_rise_capped() {
    // Force CAFLU > x7 - L: small soil deficit + small x10 means
    // CAFLU shouldn't be huge, but a small x7 - L makes the cap fire.
    // We do that by keeping the soil nearly full.
    let n = 100;
    let precip = Array1::from_elem(n, 2.0);
    let pet = Array1::from_elem(n, 0.0);

    let mut params = default_params();
    params[6] = 5.0; // x7 tiny -> soil fills fast, x7 - L stays small
    params[9] = 10.0; // x10 max -> CAFLU large

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_capillary_rise_uncapped() {
    // Tiny x10 -> CAFLU stays well below x7 - L, cap branch not taken.
    let n = 50;
    let precip = Array1::from_elem(n, 1.0);
    let pet = Array1::from_elem(n, 1.0);

    let mut params = default_params();
    params[9] = 0.01; // x10 minimum -> negligible CAFLU

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Delay-vector Construction Tests
// =============================================================================

#[test]
fn test_delay_minimum() {
    // x4 = 0.5 -> ceil(0.5)+1 = 2 elements in DL.
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let mut params = default_params();
    params[3] = 0.5;

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_maximum() {
    // x4 = 10 -> ceil(10)+1 = 11 elements in DL.
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let mut params = default_params();
    params[3] = 10.0;

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_delay_integer() {
    // x4 = 5.0 (exact integer) -> the dl[n-2] formula has a fractional
    // remainder of zero, so dl[n-2] = 1/(5 - 6 + 3) = 1/2 and
    // dl[n-1] = 1/2. Tests the boundary case.
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let mut params = default_params();
    params[3] = 5.0;

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Sensitivity Tests
// =============================================================================

#[test]
fn test_x9_sensitivity() {
    // Larger surface capacity x9 -> more rain absorbed before spill,
    // so dampens the streamflow response on the same input series.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 8.0, 0.5, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let mut params_small = default_params();
    params_small[8] = 10.0;
    let mut params_large = default_params();
    params_large[8] = 900.0;

    let flow_small =
        simulate(params_small.view(), precip.view(), pet.view()).unwrap();
    let flow_large =
        simulate(params_large.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_small.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_large.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x6_sensitivity() {
    // x6 controls how fast the ground reservoir empties: smaller =>
    // faster baseflow recession.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let mut params_fast = default_params();
    params_fast[5] = 1.0;
    let mut params_slow = default_params();
    params_slow[5] = 500.0;

    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x2_routing_sensitivity() {
    // x2 controls how fast the four cascade reservoirs drain.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let mut params_fast = default_params();
    params_fast[1] = 1.0;
    let mut params_slow = default_params();
    params_slow[1] = 100.0;

    let flow_fast =
        simulate(params_fast.view(), precip.view(), pet.view()).unwrap();
    let flow_slow =
        simulate(params_slow.view(), precip.view(), pet.view()).unwrap();

    assert!(flow_fast.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(flow_slow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 1.0f64..1000.0,
        x2 in 1.0f64..100.0,
        x3 in 1.0f64..100.0,
        x4 in 0.5f64..10.0,
        x5 in 0.01f64..0.99,
        x6 in 1.0f64..500.0,
        x7 in 1.0f64..1000.0,
        x8 in 1.0f64..100.0,
        x9 in 1.0f64..1000.0,
        x10 in 0.01f64..10.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8, x9, x10];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q >= 0.0));
    }

    #[test]
    fn prop_output_length(n in 10usize..200) {
        let defaults = default_params();
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

        let streamflow = simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        prop_assert_eq!(streamflow.len(), n);
    }

    #[test]
    fn prop_finite_output(
        x1 in 50.0f64..500.0,
        x2 in 5.0f64..50.0,
        x3 in 5.0f64..50.0,
        x4 in 1.0f64..5.0,
        x5 in 0.1f64..0.8,
        x6 in 5.0f64..200.0,
        x7 in 50.0f64..500.0,
        x8 in 5.0f64..50.0,
        x9 in 50.0f64..500.0,
        x10 in 0.1f64..5.0
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8, x9, x10];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite()));
    }
}
