use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::topmodel::{
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
    assert_eq!(defaults.len(), 7, "TOPMODEL should have 7 parameters");
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

    // x1 (quadratic routing reservoir capacity, mm): [1, 1000]
    assert_relative_eq!(bounds[[0, 0]], 1.0);
    assert_relative_eq!(bounds[[0, 1]], 1000.0);

    // x2 (exponential groundwater drainage parameter, mm): [0.1, 50]
    assert_relative_eq!(bounds[[1, 0]], 0.1);
    assert_relative_eq!(bounds[[1, 1]], 50.0);

    // x3 (interception reservoir capacity, mm): [0.1, 100]
    assert_relative_eq!(bounds[[2, 0]], 0.1);
    assert_relative_eq!(bounds[[2, 1]], 100.0);

    // x4 (routing delay, d): [0.5, 10]
    assert_relative_eq!(bounds[[3, 0]], 0.5);
    assert_relative_eq!(bounds[[3, 1]], 10.0);

    // x5 (topographic-index distribution scale, mm): [1, 200]
    assert_relative_eq!(bounds[[4, 0]], 1.0);
    assert_relative_eq!(bounds[[4, 1]], 200.0);

    // x6 (topographic-index sigmoid offset): [-10, 10]
    assert_relative_eq!(bounds[[5, 0]], -10.0);
    assert_relative_eq!(bounds[[5, 1]], 10.0);

    // x7 (groundwater PET sigmoid offset): [-10, 10]
    assert_relative_eq!(bounds[[6, 0]], -10.0);
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

#[test]
fn test_simulate_steady_state_constant_forcing() {
    // Constant forcing with P > PET should drive the model to a steady-state
    // streamflow of P - PET once reservoirs equilibrate. This is the
    // tightest mass-conservation check we can do without instrumenting
    // internal state — and it caught the original x2-bound bug.
    let (defaults, _) = init();
    let n = 365;
    let precip = Array1::from_elem(n, 5.0);
    let pet = Array1::from_elem(n, 2.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    let tail_mean: f64 =
        streamflow.slice(ndarray::s![300..]).mean().unwrap();
    assert_relative_eq!(tail_mean, 3.0, epsilon = 1e-6);
}

// =============================================================================
// Error Handling Tests
// =============================================================================

#[test]
fn test_simulate_param_count_error() {
    let wrong_params = array![100.0, 25.0, 50.0, 5.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(wrong_params.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::ParamsMismatch(7, 4))));
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
fn test_topmodel_nan_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, f64::NAN, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NonFiniteInput { .. })));
}

#[test]
fn test_topmodel_nan_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, f64::NAN, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NonFiniteInput { .. })));
}

#[test]
fn test_topmodel_negative_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, -5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NegativeInput { .. })));
}

#[test]
fn test_topmodel_negative_pet() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, -1.0, 2.0];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::NegativeInput { .. })));
}

#[test]
fn test_topmodel_empty_arrays() {
    let (defaults, _) = init();
    let precip: Array1<f64> = array![];
    let pet: Array1<f64> = array![];

    let result = simulate(defaults.view(), precip.view(), pet.view());
    assert!(matches!(result, Err(HydroError::EmptyInput { .. })));
}

#[test]
fn test_topmodel_param_above_upper_bound() {
    // x1 (1..1000) above the upper bound
    let params = array![5000.0, 25.0, 50.0, 5.0, 100.0, 0.0, 0.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { .. })
    ));
}

#[test]
fn test_topmodel_param_below_lower_bound() {
    // x2 (0.1..50) below the lower bound
    let params = array![100.0, 0.001, 50.0, 5.0, 100.0, 0.0, 0.0];
    let precip = array![10.0, 5.0, 0.0];
    let pet = array![2.0, 2.0, 2.0];

    let result = simulate(params.view(), precip.view(), pet.view());
    assert!(matches!(
        result,
        Err(HydroError::ParameterOutOfBounds { .. })
    ));
}

// =============================================================================
// Branch / Sensitivity Tests
// =============================================================================

#[test]
fn test_wet_conditions() {
    let (defaults, _) = init();
    let n = 200;
    let precip = Array1::from_elem(n, 20.0);
    let pet = Array1::from_elem(n, 5.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(streamflow.sum() > 0.0);
}

#[test]
fn test_dry_conditions() {
    let (defaults, _) = init();
    let n = 200;
    let precip = Array1::from_elem(n, 0.5);
    let pet = Array1::from_elem(n, 10.0);

    let streamflow =
        simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x1_routing_capacity_sensitivity() {
    // Larger x1 → quadratic routing reservoir empties more slowly,
    // distributing flow over more time steps and dampening peak Qr.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 2.0, 1.0, 43);

    let p_small = array![10.0, 25.0, 50.0, 5.0, 100.0, 0.0, 0.0];
    let p_large = array![800.0, 25.0, 50.0, 5.0, 100.0, 0.0, 0.0];

    let q_small = simulate(p_small.view(), precip.view(), pet.view()).unwrap();
    let q_large = simulate(p_large.view(), precip.view(), pet.view()).unwrap();

    assert!(q_small.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(q_large.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x2_baseflow_sensitivity() {
    // x2 sets both the baseflow scale and the recession length. Smaller
    // x2 → less baseflow at saturation. We just check both extremes
    // produce finite, non-negative flow.
    let n = 365;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let p_small = array![100.0, 1.0, 50.0, 5.0, 100.0, 0.0, 0.0];
    let p_large = array![100.0, 40.0, 50.0, 5.0, 100.0, 0.0, 0.0];

    let q_small = simulate(p_small.view(), precip.view(), pet.view()).unwrap();
    let q_large = simulate(p_large.view(), precip.view(), pet.view()).unwrap();

    assert!(q_small.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(q_large.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x3_interception_extremes() {
    // Very small x3 means almost everything spills as Pr; very large x3
    // means S almost never overflows. Both must stay numerically clean.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let p_low = array![100.0, 25.0, 0.5, 5.0, 100.0, 0.0, 0.0];
    let p_high = array![100.0, 25.0, 99.0, 5.0, 100.0, 0.0, 0.0];

    let q_low = simulate(p_low.view(), precip.view(), pet.view()).unwrap();
    let q_high = simulate(p_high.view(), precip.view(), pet.view()).unwrap();

    assert!(q_low.iter().all(|&q| q.is_finite() && q >= 0.0));
    assert!(q_high.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_x6_x7_sigmoid_offsets() {
    // x6 and x7 shift the two sigmoids that partition Pr→Ps and E→Et.
    // Push them to both extremes to exercise the saturating regimes.
    let n = 200;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    for &x6 in &[-9.5, 9.5] {
        for &x7 in &[-9.5, 9.5] {
            let params = array![100.0, 25.0, 50.0, 5.0, 100.0, x6, x7];
            let q =
                simulate(params.view(), precip.view(), pet.view()).unwrap();
            assert!(
                q.iter().all(|&v| v.is_finite() && v >= 0.0),
                "non-finite or negative q with x6={x6}, x7={x7}"
            );
        }
    }
}

#[test]
fn test_delay_parameter_short() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![100.0, 25.0, 50.0, 0.5, 100.0, 0.0, 0.0];
    let q = simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(q.iter().all(|&v| v.is_finite() && v >= 0.0));
}

#[test]
fn test_delay_parameter_long() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![100.0, 25.0, 50.0, 10.0, 100.0, 0.0, 0.0];
    let q = simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(q.iter().all(|&v| v.is_finite() && v >= 0.0));
}

#[test]
fn test_delay_parameter_integer() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    let params = array![100.0, 25.0, 50.0, 3.0, 100.0, 0.0, 0.0];
    let q = simulate(params.view(), precip.view(), pet.view()).unwrap();
    assert!(q.iter().all(|&v| v.is_finite() && v >= 0.0));
}

#[test]
fn test_all_param_corners() {
    // Iterate each parameter to its low and high bound with the others at
    // their default — exercises sigmoid saturation, exp() extremes, and
    // unit-hydrograph boundary cases.
    let (defaults, bounds) = init();
    let n = 80;
    let precip = helpers::generate_precipitation(n, 4.0, 0.25, 17);
    let pet = helpers::generate_pet(n, 2.5, 1.0, 19);

    for i in 0..7 {
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
        x1 in 1.0f64..1000.0,
        x2 in 0.1f64..50.0,
        x3 in 0.1f64..100.0,
        x4 in 0.5f64..10.0,
        x5 in 1.0f64..200.0,
        x6 in -10.0f64..10.0,
        x7 in -10.0f64..10.0,
    ) {
        let params = array![x1, x2, x3, x4, x5, x6, x7];
        let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(50, 3.0, 1.0, 43);

        let streamflow =
            simulate(params.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q >= 0.0 && q.is_finite()));
    }

    #[test]
    fn prop_output_length(n in 10usize..200) {
        let (defaults, _) = init();
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
        let streamflow =
            simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        prop_assert_eq!(streamflow.len(), n);
    }

    #[test]
    fn prop_finite_under_random_forcing(
        seed in 0u64..1000,
        precip_mean in 0.5f64..15.0,
        pet_mean in 0.5f64..6.0,
    ) {
        let (defaults, _) = init();
        let precip =
            helpers::generate_precipitation(120, precip_mean, 0.3, seed);
        let pet = helpers::generate_pet(120, pet_mean, 1.0, seed + 1);

        let streamflow =
            simulate(defaults.view(), precip.view(), pet.view()).unwrap();
        prop_assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
    }
}
