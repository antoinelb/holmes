use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::xinanjiang::{
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
        8,
        "XINANJIANG model should have 8 parameters"
    );
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
            "Parameter {}: lower ({}) should be less than upper ({})",
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

    // x1 (flow partitioning between fast and slow routing): [0.01, 0.99]
    assert_relative_eq!(bounds[[0, 0]], 0.01);
    assert_relative_eq!(bounds[[0, 1]], 0.99);

    // x2 (fast reservoir emptying constant): [1, 20]
    // Lower tightened from HOOPLA's 0 so T -= T/x2 can never drive T negative.
    assert_relative_eq!(bounds[[1, 0]], 1.0);
    assert_relative_eq!(bounds[[1, 1]], 20.0);

    // x3 (slow reservoir emptying multiplier): [1, 50]
    // Lower tightened so that x2*x3 >= 1 across all valid (x2, x3) pairs.
    assert_relative_eq!(bounds[[2, 0]], 1.0);
    assert_relative_eq!(bounds[[2, 1]], 50.0);

    // x4 (free-water reservoir capacity): [1, 500]
    assert_relative_eq!(bounds[[3, 0]], 1.0);
    assert_relative_eq!(bounds[[3, 1]], 500.0);

    // x5 (soil reservoir capacity): [1, 2000]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 2000.0);

    // x6 (unit hydrograph delay): [0.5, 10]
    assert_relative_eq!(bounds[[5, 0]], 0.5);
    assert_relative_eq!(bounds[[5, 1]], 10.0);

    // x7 (free-water reservoir emptying constant): [1, 50]
    // Lower tightened so R -= R/x7 can never drive R negative.
    assert_relative_eq!(bounds[[6, 0]], 1.0);
    assert_relative_eq!(bounds[[6, 1]], 50.0);

    // x8 (saturation-excess distribution exponent): [0.01, 5]
    assert_relative_eq!(bounds[[7, 0]], 0.01);
    assert_relative_eq!(bounds[[7, 1]], 5.0);
}

// =============================================================================
// Simulation Tests
// =============================================================================

#[test]
fn test_simulate_basic() {
    let (defaults, _) = init();
    let n = 365;
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
    let n = 200;
    let precip = Array1::zeros(n);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q >= 0.0 && q.is_finite()),
        "All values should be non-negative and finite"
    );
    // With no precip, flow must strictly decay after the initial reservoirs
    // drain — the last value should be at most the first few.
    assert!(streamflow[n - 1] <= streamflow[10]);
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
fn test_simulate_param_count_error_too_few() {
    let wrong_params = array![0.5, 5.0, 10.0, 100.0, 500.0]; // 5 instead of 8
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(8, 5))));
}

#[test]
fn test_simulate_param_count_error_too_many() {
    let wrong_params =
        array![0.5, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 1.0, 0.5]; // 9
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(8, 9))));
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
fn test_xinanjiang_nan_precipitation() {
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
fn test_xinanjiang_nan_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, f64::NAN, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(
        matches!(result, Err(HydroError::NonFiniteInput { .. })),
        "Should reject NaN in pet"
    );
}

#[test]
fn test_xinanjiang_infinity_input() {
    let (defaults, _) = init();
    let precip = array![10.0, f64::INFINITY, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NonFiniteInput { .. })));
}

#[test]
fn test_xinanjiang_negative_precipitation() {
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
fn test_xinanjiang_negative_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, -1.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NegativeInput { .. })));
}

#[test]
fn test_xinanjiang_empty_arrays() {
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
fn test_xinanjiang_x1_below_lower_bound() {
    // x1 = 0.001 is below the [0.01, 0.99] lower bound
    let params = array![0.001, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x1", .. })
    ));
}

#[test]
fn test_xinanjiang_x1_above_upper_bound() {
    let params = array![1.5, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x1", .. })
    ));
}

#[test]
fn test_xinanjiang_x2_at_zero_rejected() {
    // HOOPLA allows x2=0 but HOLMES tightened to 1.0 to keep T non-negative.
    let params = array![0.5, 0.0, 10.0, 100.0, 500.0, 2.0, 10.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x2", .. })
    ));
}

#[test]
fn test_xinanjiang_x3_below_one_rejected() {
    // HOOPLA allows x3 < 1 but HOLMES tightened to 1.0 so that x2*x3 >= 1
    // and M -= M/(x2*x3) can never drive M negative.
    let params = array![0.5, 5.0, 0.5, 100.0, 500.0, 2.0, 10.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x3", .. })
    ));
}

#[test]
fn test_xinanjiang_x4_at_zero_rejected() {
    // x4 = 0 would cause division by zero in R/x4 and (1+x8)*x4 calls.
    let params = array![0.5, 5.0, 10.0, 0.0, 500.0, 2.0, 10.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x4", .. })
    ));
}

#[test]
fn test_xinanjiang_x5_at_zero_rejected() {
    // x5 = 0 would cause division by zero in S/x5 checks.
    let params = array![0.5, 5.0, 10.0, 100.0, 0.0, 2.0, 10.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x5", .. })
    ));
}

#[test]
fn test_xinanjiang_x6_below_half_rejected() {
    // x6 = 0.1 is below 0.5 — would produce a degenerate one-tap UH.
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 0.1, 10.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x6", .. })
    ));
}

#[test]
fn test_xinanjiang_x7_at_zero_rejected() {
    // HOOPLA allows x7=0 but HOLMES tightened to 1.0 so R stays non-negative.
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 2.0, 0.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x7", .. })
    ));
}

#[test]
fn test_xinanjiang_x8_at_zero_rejected() {
    // x8 = 0 would make 1/(1+x8) = 1 (ok) but HOLMES keeps a small positive
    // lower bound to stay strictly away from degenerate exponents.
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 0.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x8", .. })
    ));
}

#[test]
fn test_xinanjiang_nan_parameter_rejected() {
    let params = array![0.5, 5.0, 10.0, f64::NAN, 500.0, 2.0, 10.0, 1.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { name: "x4", .. })
    ));
}

// =============================================================================
// Branch / Parameter Sensitivity Tests
// =============================================================================

#[test]
fn test_wet_conditions_p_greater_than_e() {
    let (defaults, _) = init();
    let n = 200;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 2.0);

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
    // Long dry period exercises the en > 0 branch heavily, including the
    // S/x5 < 0.09 branch once the soil has drained enough.
    let (defaults, _) = init();
    let n = 500;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 8.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle dry conditions without numerical issues"
    );
}

#[test]
fn test_equal_p_and_e_edge_case() {
    // P == E exactly: both Pn and En are zero; neither production branch
    // fires and routing runs with Ir = 0.
    let (defaults, _) = init();
    let n = 100;
    let precip = Array1::from_elem(n, 3.0);
    let pet = Array1::from_elem(n, 3.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_water_balance_monotonicity_in_pet() {
    // Halving PET must not decrease total streamflow.
    let (defaults, _) = init();
    let n = 500;
    let precip = helpers::generate_precipitation(n, 5.0, 0.5, 42);
    let pet_full = helpers::generate_pet(n, 4.0, 1.0, 43);
    let pet_half = pet_full.clone() * 0.5;

    let q_full =
        simulate(defaults.view(), precip.view(), pet_full.view()).unwrap();
    let q_half =
        simulate(defaults.view(), precip.view(), pet_half.view()).unwrap();
    assert!(
        q_half.sum() >= q_full.sum(),
        "Lower PET must not decrease total streamflow"
    );
}

#[test]
fn test_et_branch_high_soil_saturation() {
    // S starts at x5 (full) so S/x5 = 1 >= 0.9 on step one.
    // Heavy PET over a single long dry spell keeps us in the "full" branch.
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 1.0];
    let n = 10;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 1.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_et_branch_intermediate_soil_saturation() {
    // Tight x5 so a few PET steps drop S into the intermediate band
    // 0.09 <= S/x5 < 0.9 — exercises the linear-interpolation ET branch.
    let params = array![0.5, 5.0, 10.0, 100.0, 10.0, 2.0, 10.0, 1.0];
    let n = 50;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 0.5);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_et_branch_low_soil_saturation() {
    // After a sustained dry spell S/x5 drops below 0.09 — the third ET branch.
    let params = array![0.5, 5.0, 10.0, 100.0, 10.0, 2.0, 10.0, 1.0];
    let n = 500;
    let precip = Array1::zeros(n);
    let pet = Array1::from_elem(n, 2.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_heavy_rain_full_r_reservoir() {
    // Heavy rain with tight R capacity forces the min(x4, R+Pr2) clamp
    // to fire every step, producing Qs0 overflow.
    let params = array![0.5, 5.0, 10.0, 10.0, 50.0, 2.0, 2.0, 1.0];
    let n = 100;
    let precip = Array1::from_elem(n, 50.0);
    let pet = Array1::from_elem(n, 1.0);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(
        streamflow.sum() > 0.0,
        "Heavy rain should produce positive flow"
    );
}

#[test]
fn test_x1_full_fast_routing() {
    // x1 near 1: almost all of Ir goes into the fast reservoir T
    let params = array![0.99, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 1.0];
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x1_full_slow_routing() {
    // x1 near 0: almost all of Ir goes into the slow reservoir M
    let params = array![0.01, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 1.0];
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x8_exponent_low() {
    // x8 near lower bound: very sharp saturation-excess curve
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 0.01];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x8_exponent_high() {
    // x8 near upper bound: gentle saturation-excess curve
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 2.0, 10.0, 5.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Unit-hydrograph edge cases
// =============================================================================

#[test]
fn test_uh_delay_minimum() {
    // x6 = 0.5 (lower bound): size = ceil(0.5) + 1 = 2 — shortest valid UH.
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 0.5, 10.0, 1.0];
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_delay_integer() {
    // x6 = 5.0 (exact integer mid-range)
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 5.0, 10.0, 1.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_delay_non_integer() {
    // x6 = 3.7 (fractional delay exercises the two-tap weighting formula)
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 3.7, 10.0, 1.0];
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_uh_delay_maximum() {
    // x6 = 10 (upper bound): longest UH allowed
    let params = array![0.5, 5.0, 10.0, 100.0, 500.0, 10.0, 10.0, 1.0];
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let streamflow =
        simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_streamflow(
        x1 in 0.01f64..0.99,
        x2 in 1.0f64..20.0,
        x3 in 1.0f64..50.0,
        x4 in 1.0f64..500.0,
        x5 in 1.0f64..2000.0,
        x6 in 0.5f64..10.0,
        x7 in 1.0f64..50.0,
        x8 in 0.01f64..5.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let q = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(q.iter().all(|&v| v >= 0.0 && v.is_finite()));
    }

    #[test]
    fn prop_output_length(n in 10usize..200) {
        let (defaults, _) = init();
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

        let q = simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        prop_assert_eq!(q.len(), n);
    }

    #[test]
    fn prop_bound_corners_are_stable(
        // Exercise every corner of the parameter box — the tightened lower
        // bounds on x2, x3, x7 are where numerical stability matters most.
        x1 in prop_oneof![Just(0.01f64), Just(0.99f64)],
        x2 in prop_oneof![Just(1.0f64), Just(20.0f64)],
        x3 in prop_oneof![Just(1.0f64), Just(50.0f64)],
        x4 in prop_oneof![Just(1.0f64), Just(500.0f64)],
        x5 in prop_oneof![Just(1.0f64), Just(2000.0f64)],
        x6 in prop_oneof![Just(0.5f64), Just(10.0f64)],
        x7 in prop_oneof![Just(1.0f64), Just(50.0f64)],
        x8 in prop_oneof![Just(0.01f64), Just(5.0f64)],
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7, x8];
        let precip = helpers::generate_precipitation(100, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(100, 3.0, 1.0, 43);

        let q = simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(q.iter().all(|&v| v.is_finite() && v >= 0.0));
    }
}
