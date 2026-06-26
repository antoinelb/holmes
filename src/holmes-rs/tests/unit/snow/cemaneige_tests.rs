use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::snow::cemaneige::{
    compute_normalization, init, param_names, simulate,
};
use holmes_rs::snow::utils::{
    validate_day_of_year, validate_output, validate_temperature,
};
use holmes_rs::snow::SnowError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_init_bounds_shape() {
    let (defaults, bounds) = init();
    assert_eq!(defaults.len(), 3, "CemaNeige should have 3 parameters");
    assert_eq!(
        bounds.shape(),
        &[3, 2],
        "Bounds should be 3x2 (params x [lower, upper])"
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
fn test_init_specific_bounds() {
    let (_, bounds) = init();

    // ctg: [0, 1]
    assert_relative_eq!(bounds[[0, 0]], 0.0);
    assert_relative_eq!(bounds[[0, 1]], 1.0);

    // kf: [0, 20]
    assert_relative_eq!(bounds[[1, 0]], 0.0);
    assert_relative_eq!(bounds[[1, 1]], 20.0);

    // qnbv: [0, 2000]
    assert_relative_eq!(bounds[[2, 0]], 0.0);
    assert_relative_eq!(bounds[[2, 1]], 2000.0);
}

#[test]
fn test_param_names() {
    assert_eq!(param_names.len(), 3);
    assert_eq!(param_names, &["ctg", "kf", "qnbv"]);
}

// =============================================================================
// Simulation Tests
// =============================================================================

#[test]
fn test_no_snow_warm_temps() {
    // When all temperatures are above freezing, effective precip ≈ precip (no snow)
    let (defaults, _) = init();
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let temp = Array1::from_elem(n, 10.0); // All warm
    let doy = helpers::generate_doy(180, n); // Summer (just for consistency)
    let elevation_layers =
        helpers::generate_elevation_layers(5, 500.0, 1500.0);
    let median_elevation = 1000.0;

    let effective_precip = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
    )
    .unwrap();

    // With warm temps, effective precip should be close to original precip
    let total_precip: f64 = precip.sum();
    let total_effective: f64 = effective_precip.sum();

    // Allow some difference due to model dynamics, but should be similar
    assert!(
        (total_effective - total_precip).abs() / total_precip.max(1.0) < 0.5,
        "Warm temps should pass most precipitation through as liquid"
    );
}

#[test]
fn test_all_snow_cold_temps() {
    // When all temperatures are well below freezing, precipitation accumulates as snow
    let (defaults, _) = init();
    let n = 30;
    let precip = Array1::from_elem(n, 5.0); // Constant precip
    let temp = Array1::from_elem(n, -10.0); // All cold (below -1°C threshold)
    let doy = helpers::generate_doy(1, n); // Winter
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

    let effective_precip = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
    )
    .unwrap();

    // With very cold temps and no melt, effective precip should be low
    // (snow accumulates instead of producing runoff)
    let total_effective: f64 = effective_precip.sum();
    let total_precip: f64 = precip.sum();

    assert!(
        total_effective < total_precip * 0.5,
        "Cold temps should accumulate snow, reducing effective precip"
    );
}

#[test]
fn test_accumulation_melt_cycle() {
    // Winter accumulation followed by spring melt
    let (defaults, _) = init();

    // Winter: cold with precipitation
    let n_winter = 60;
    let precip_winter = Array1::from_elem(n_winter, 3.0);
    let temp_winter = Array1::from_elem(n_winter, -5.0);
    let doy_winter = helpers::generate_doy(1, n_winter);

    // Spring: warming with some precip
    let n_spring = 60;
    let precip_spring = Array1::from_elem(n_spring, 2.0);
    let temp_spring: Array1<f64> = Array1::from_iter(
        (0..n_spring).map(|i| -5.0 + (i as f64) * 0.2), // Gradual warming
    );
    let doy_spring = helpers::generate_doy(61, n_spring);

    // Combine
    let precip = ndarray::concatenate(
        ndarray::Axis(0),
        &[precip_winter.view(), precip_spring.view()],
    )
    .unwrap();
    let temp = ndarray::concatenate(
        ndarray::Axis(0),
        &[temp_winter.view(), temp_spring.view()],
    )
    .unwrap();
    let doy = ndarray::concatenate(
        ndarray::Axis(0),
        &[doy_winter.view(), doy_spring.view()],
    )
    .unwrap();

    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

    let effective_precip = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
    )
    .unwrap();

    // During spring melt, effective precip should increase
    let winter_mean: f64 = effective_precip
        .slice(ndarray::s![..n_winter])
        .mean()
        .unwrap();
    let spring_mean: f64 = effective_precip
        .slice(ndarray::s![n_winter..])
        .mean()
        .unwrap();

    // Spring should have higher effective precip due to melt
    assert!(
        spring_mean > winter_mean,
        "Spring melt should increase effective precipitation"
    );
}

#[test]
fn test_multiple_elevation_layers() {
    // Higher elevation layers should accumulate more snow
    let (defaults, _) = init();
    let n = 60;
    let precip = Array1::from_elem(n, 3.0);
    let temp = Array1::from_elem(n, -2.0); // Near freezing
    let doy = helpers::generate_doy(1, n);

    // Test with multiple elevation bands
    let elevation_layers =
        helpers::generate_elevation_layers(5, 500.0, 2500.0);
    let median_elevation = 1500.0;

    let effective_precip = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
    )
    .unwrap();

    assert_eq!(effective_precip.len(), n);
    assert!(
        effective_precip.iter().all(|&p| p.is_finite() && p >= 0.0),
        "All values should be valid"
    );
}

#[test]
fn test_simulate_output_length() {
    let (defaults, _) = init();
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

    for n in [10, 100, 365] {
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let temp = helpers::generate_temperature(n, 5.0, 15.0, 2.0, 43);
        let doy = helpers::generate_doy(1, n);

        let effective_precip = simulate(
            defaults.view(),
            precip.view(),
            temp.view(),
            doy.view(),
            elevation_layers.view(),
            median_elevation,
        )
        .unwrap();

        assert_eq!(effective_precip.len(), n);
    }
}

// =============================================================================
// Error Handling Tests
// =============================================================================

#[test]
fn test_param_count_error() {
    let wrong_params = array![0.5, 5.0]; // Only 2 params instead of 3
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        wrong_params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(matches!(result, Err(SnowError::ParamsMismatch(3, 2))));
}

#[test]
fn test_length_mismatch() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0]; // Length mismatch
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(matches!(result, Err(SnowError::LengthMismatch(3, 2, 3))));
}

#[test]
fn test_cemaneige_empty_precipitation() {
    let (defaults, _) = init();
    let precip: Array1<f64> = array![];
    let temp: Array1<f64> = array![];
    let doy: Array1<usize> = array![];
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::EmptyInput {
                name: "precipitation"
            })
        ),
        "Should reject empty precipitation array"
    );
}

#[test]
fn test_cemaneige_negative_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, -5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::NegativeInput {
                name: "precipitation",
                index: 1,
                ..
            })
        ),
        "Should reject negative precipitation"
    );
}

#[test]
fn test_cemaneige_nan_in_precipitation() {
    let (defaults, _) = init();
    let precip = array![10.0, f64::NAN, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::NonFiniteInput {
                name: "precipitation",
                ..
            })
        ),
        "Should reject NaN in precipitation"
    );
}

#[test]
fn test_cemaneige_nan_in_temperature() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, f64::NAN, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::NonFiniteInput {
                name: "temperature",
                ..
            })
        ),
        "Should reject NaN in temperature"
    );
}

#[test]
fn test_cemaneige_temperature_too_low() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, -150.0, 0.0]; // -150 is below -100 min
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::TemperatureOutOfRange {
                index: 1,
                min: -100.0,
                max: 100.0,
                ..
            })
        ),
        "Should reject temperature below -100°C"
    );
}

#[test]
fn test_cemaneige_temperature_too_high() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 150.0, 0.0]; // 150 is above 100 max
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::TemperatureOutOfRange {
                index: 1,
                min: -100.0,
                max: 100.0,
                ..
            })
        ),
        "Should reject temperature above 100°C"
    );
}

#[test]
fn test_cemaneige_invalid_day_of_year_zero() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 0, 3]; // 0 is invalid
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::InvalidDayOfYear { index: 1, value: 0 })
        ),
        "Should reject day of year 0"
    );
}

#[test]
fn test_cemaneige_invalid_day_of_year_367() {
    let (defaults, _) = init();
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 367, 3]; // 367 is invalid
    let elevation_layers = array![1000.0];

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::InvalidDayOfYear {
                index: 1,
                value: 367
            })
        ),
        "Should reject day of year > 366"
    );
}

#[test]
fn test_cemaneige_param_ctg_out_of_bounds() {
    let (_, bounds) = init();
    let ctg = bounds[[0, 1]] + 1.0; // just above ctg's upper bound
    let params = array![ctg, 5.0, 350.0];
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::ParameterOutOfBounds { name: "ctg", .. })
        ),
        "Should reject ctg above its upper bound"
    );
}

#[test]
fn test_cemaneige_param_kf_out_of_bounds() {
    let (_, bounds) = init();
    let kf = bounds[[1, 1]] + 1.0; // just above kf's upper bound
    let params = array![0.5, kf, 350.0];
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::ParameterOutOfBounds { name: "kf", .. })
        ),
        "Should reject kf above its upper bound"
    );
}

#[test]
fn test_cemaneige_param_qnbv_out_of_bounds() {
    let (_, bounds) = init();
    let qnbv = bounds[[2, 1]] + 1.0; // just above qnbv's upper bound
    let params = array![0.5, 5.0, qnbv];
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::ParameterOutOfBounds { name: "qnbv", .. })
        ),
        "Should reject qnbv above its upper bound"
    );
}

#[test]
fn test_cemaneige_param_ctg_negative() {
    let (_, bounds) = init();
    let ctg = bounds[[0, 0]] - 1.0; // just below ctg's lower bound
    let params = array![ctg, 5.0, 350.0];
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::ParameterOutOfBounds { name: "ctg", .. })
        ),
        "Should reject ctg below its lower bound"
    );
}

#[test]
fn test_cemaneige_param_kf_negative() {
    let (_, bounds) = init();
    let kf = bounds[[1, 0]] - 1.0; // just below kf's lower bound
    let params = array![0.5, kf, 350.0];
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::ParameterOutOfBounds { name: "kf", .. })
        ),
        "Should reject kf below its lower bound"
    );
}

#[test]
fn test_cemaneige_param_qnbv_too_low() {
    let (_, bounds) = init();
    let qnbv = bounds[[2, 0]] - 1.0; // just below qnbv's lower bound
    let params = array![0.5, 5.0, qnbv];
    let precip = array![10.0, 5.0, 0.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers = array![1000.0];

    let result = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::ParameterOutOfBounds { name: "qnbv", .. })
        ),
        "Should reject qnbv below its lower bound"
    );
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_nonnegative_effective_precip(
        ctg in 0.0f64..1.0,
        kf in 0.0f64..20.0,
        qnbv in init().1[[2, 0]]..init().1[[2, 1]]
    ) {
        let params = array![ctg, kf, qnbv];
        let precip = helpers::generate_precipitation(30, 5.0, 0.3, 42);
        let temp = helpers::generate_temperature(30, 5.0, 10.0, 2.0, 43);
        let doy = helpers::generate_doy(1, 30);
        let elevation_layers = array![1000.0];

        let effective_precip = simulate(
            params.view(),
            precip.view(),
            temp.view(),
            doy.view(),
            elevation_layers.view(),
            1000.0,
        ).unwrap();

        prop_assert!(effective_precip.iter().all(|&p| p >= 0.0));
    }

    #[test]
    fn prop_finite_output(
        ctg in 0.1f64..0.9,
        kf in 1.0f64..15.0,
        qnbv in init().1[[2, 0]]..init().1[[2, 1]]
    ) {
        let params = array![ctg, kf, qnbv];
        let precip = helpers::generate_precipitation(30, 5.0, 0.3, 42);
        let temp = helpers::generate_temperature(30, 5.0, 10.0, 2.0, 43);
        let doy = helpers::generate_doy(1, 30);
        let elevation_layers = array![1000.0];

        let effective_precip = simulate(
            params.view(),
            precip.view(),
            temp.view(),
            doy.view(),
            elevation_layers.view(),
            1000.0,
        ).unwrap();

        prop_assert!(effective_precip.iter().all(|&p| p.is_finite()));
    }

    #[test]
    fn prop_output_length(n in 10usize..100) {
        let (defaults, _) = init();
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
        let temp = helpers::generate_temperature(n, 5.0, 10.0, 2.0, 43);
        let doy = helpers::generate_doy(1, n);
        let elevation_layers = array![1000.0];

        let effective_precip = simulate(
            defaults.view(),
            precip.view(),
            temp.view(),
            doy.view(),
            elevation_layers.view(),
            1000.0,
        ).unwrap();

        prop_assert_eq!(effective_precip.len(), n);
    }
}

// =============================================================================
// Branch Coverage Tests
// =============================================================================

#[test]
fn test_solid_fraction_above_3c() {
    // Temperature > 3°C: solid_fraction = 0 (all liquid)
    let (defaults, _) = init();
    let n = 30;
    let precip = Array1::from_elem(n, 5.0);
    let temp = Array1::from_elem(n, 10.0); // Well above 3°C
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    let effective_precip = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    // All liquid precipitation, effective precip should closely match precip
    assert!(effective_precip.iter().all(|&p| p.is_finite() && p >= 0.0));
}

#[test]
fn test_solid_fraction_below_minus1c() {
    // Temperature < -1°C: solid_fraction = 1 (all snow)
    let (defaults, _) = init();
    let n = 30;
    let precip = Array1::from_elem(n, 5.0);
    let temp = Array1::from_elem(n, -10.0); // Well below -1°C
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    let effective_precip = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    // All solid precipitation (snow), low effective precip
    assert!(effective_precip.iter().all(|&p| p.is_finite() && p >= 0.0));
}

#[test]
fn test_solid_fraction_transition_zone() {
    // Temperature between -1°C and 3°C: mixed precipitation
    let (defaults, _) = init();
    let n = 30;
    let precip = Array1::from_elem(n, 5.0);
    let temp = Array1::from_elem(n, 1.0); // In transition zone
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    let effective_precip = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    assert!(effective_precip.iter().all(|&p| p.is_finite() && p >= 0.0));
}

#[test]
fn test_melt_conditions() {
    // Test snowmelt when thermal_state >= 0 and temperature > 0
    let params = array![0.5, 10.0, 350.0]; // Higher kf for more melt
    let n = 60;

    // Cold period to accumulate snow, then warm period for melt
    let mut precip = Array1::from_elem(n, 5.0);
    let mut temp = Array1::from_elem(n, -10.0);

    // Warm up in second half
    for i in 30..60 {
        temp[i] = 10.0;
        precip[i] = 0.0; // No new precip during melt
    }

    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    let effective_precip = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    // During melt period, should see meltwater contribution
    let melt_period_sum: f64 = effective_precip.slice(ndarray::s![30..]).sum();
    assert!(
        melt_period_sum > 0.0,
        "Should have meltwater during warm period"
    );
}

#[test]
fn test_no_melt_cold_conditions() {
    // Test that no melt occurs when temperature is always cold
    let params = array![0.5, 10.0, 350.0];
    let n = 30;
    let precip = Array1::from_elem(n, 5.0);
    let temp = Array1::from_elem(n, -20.0); // Very cold
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    let effective_precip = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    // All precipitation should accumulate as snow, very low effective precip
    let total_effective: f64 = effective_precip.sum();
    assert!(
        total_effective < precip.sum(),
        "Cold conditions should accumulate snow"
    );
}

#[test]
fn test_ctg_parameter_sensitivity() {
    // ctg controls thermal state inertia
    let n = 60;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let temp = helpers::generate_temperature(n, 0.0, 10.0, 2.0, 43);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    // Low ctg (quick thermal response)
    let params_low = array![0.1, 5.0, 350.0];
    let effective_low = simulate(
        params_low.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    // High ctg (slow thermal response)
    let params_high = array![0.9, 5.0, 350.0];
    let effective_high = simulate(
        params_high.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    assert!(effective_low.iter().all(|&p| p.is_finite() && p >= 0.0));
    assert!(effective_high.iter().all(|&p| p.is_finite() && p >= 0.0));
}

#[test]
fn test_kf_parameter_sensitivity() {
    // kf controls melt rate
    let n = 60;

    // Accumulation then melt scenario
    let mut precip = Array1::from_elem(n, 5.0);
    let mut temp = Array1::from_elem(n, -10.0);
    for i in 30..60 {
        temp[i] = 10.0;
        precip[i] = 0.0;
    }

    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    // Low kf (slow melt)
    let params_low_kf = array![0.5, 1.0, 350.0];
    let effective_low = simulate(
        params_low_kf.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    // High kf (fast melt)
    let params_high_kf = array![0.5, 20.0, 350.0];
    let effective_high = simulate(
        params_high_kf.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    assert!(effective_low.iter().all(|&p| p.is_finite() && p >= 0.0));
    assert!(effective_high.iter().all(|&p| p.is_finite() && p >= 0.0));

    // Higher kf should produce more meltwater during melt period
    let melt_low: f64 = effective_low.slice(ndarray::s![30..]).sum();
    let melt_high: f64 = effective_high.slice(ndarray::s![30..]).sum();
    assert!(melt_high >= melt_low, "Higher kf should produce more melt");
}

#[test]
fn test_qnbv_parameter_sensitivity() {
    // qnbv controls snowpack threshold for melt factor
    let n = 60;

    let mut precip = Array1::from_elem(n, 5.0);
    let mut temp = Array1::from_elem(n, -5.0);
    for i in 30..60 {
        temp[i] = 5.0;
        precip[i] = 0.0;
    }

    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    // Low qnbv
    let params_low = array![0.5, 5.0, 100.0];
    let effective_low = simulate(
        params_low.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    // High qnbv
    let params_high = array![0.5, 5.0, 700.0];
    let effective_high = simulate(
        params_high.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    assert!(effective_low.iter().all(|&p| p.is_finite() && p >= 0.0));
    assert!(effective_high.iter().all(|&p| p.is_finite() && p >= 0.0));
}

#[test]
fn test_cemaneige_qnbv_zero_lower_bound() {
    // qnbv = 0 is the lower bound, making g_threshold = 0. Without the guard
    // this divides by zero in the melt-factor ratio. The guard must keep the
    // melt factor saturated (fnts = 1) and the output finite and non-negative.
    let n = 60;
    let mut precip = Array1::from_elem(n, 5.0);
    let mut temp = Array1::from_elem(n, -5.0);
    for i in 30..60 {
        temp[i] = 5.0;
        precip[i] = 0.0;
    }
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    let (defaults, bounds) = init();
    let params = array![defaults[0], defaults[1], bounds[[2, 0]]]; // qnbv at lower bound
    let effective = simulate(
        params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    )
    .unwrap();

    assert!(
        effective.iter().all(|&p| p.is_finite() && p >= 0.0),
        "qnbv at its lower bound must keep effective precipitation finite and non-negative"
    );
    // Snow accumulated in the cold half must still melt in the warm half.
    assert!(
        effective.iter().skip(30).any(|&p| p > 0.0),
        "saturated melt factor should still melt the snowpack"
    );
}

#[test]
fn test_elevation_offset_effect() {
    // Higher elevations should be colder and accumulate more snow
    let (defaults, _) = init();
    let n = 30;
    let precip = Array1::from_elem(n, 5.0);
    let temp = Array1::from_elem(n, 1.0); // Near transition temperature
    let doy = helpers::generate_doy(1, n);

    // Low elevation range
    let low_elev = array![500.0, 600.0, 700.0];
    let effective_low = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        low_elev.view(),
        600.0,
    )
    .unwrap();

    // High elevation range
    let high_elev = array![2000.0, 2100.0, 2200.0];
    let effective_high = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        high_elev.view(),
        2100.0,
    )
    .unwrap();

    assert!(effective_low.iter().all(|&p| p.is_finite() && p >= 0.0));
    assert!(effective_high.iter().all(|&p| p.is_finite() && p >= 0.0));
}

#[test]
fn test_cemaneige_empty_elevation_layers() {
    let (defaults, _) = init();
    let precip = array![5.0, 5.0, 5.0];
    let temp = array![0.0, 0.0, 0.0];
    let doy = array![1_usize, 2, 3];
    let elevation_layers: Array1<f64> = Array1::from_vec(vec![]);

    let result = simulate(
        defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
    );
    assert!(
        matches!(
            result,
            Err(SnowError::EmptyInput {
                name: "elevation_layers"
            })
        ),
        "Should reject empty elevation_layers array"
    );
}

// =============================================================================
// Direct Utility Function Tests
// =============================================================================

#[test]
fn test_validate_day_of_year_empty() {
    let doy: Array1<usize> = array![];
    let result = validate_day_of_year(doy.view());
    assert!(
        matches!(
            result,
            Err(SnowError::EmptyInput {
                name: "day_of_year"
            })
        ),
        "Should reject empty day_of_year array"
    );
}

#[test]
fn test_validate_output_nan() {
    let arr = array![1.0, f64::NAN, 3.0];
    let result = validate_output(arr.view(), "test");
    assert!(
        matches!(
            result,
            Err(SnowError::NumericalError {
                context: "test",
                ..
            })
        ),
        "Should reject NaN in output"
    );
}

#[test]
fn test_validate_output_infinity() {
    let arr = array![1.0, f64::INFINITY, 3.0];
    let result = validate_output(arr.view(), "test context");
    assert!(
        matches!(
            result,
            Err(SnowError::NumericalError {
                context: "test context",
                ..
            })
        ),
        "Should reject Infinity in output"
    );
}

#[test]
fn test_validate_output_valid() {
    let arr = array![1.0, 2.0, 3.0];
    let result = validate_output(arr.view(), "test");
    assert!(result.is_ok(), "Should accept valid output");
}

#[test]
fn test_validate_temperature_valid() {
    let temp = array![-50.0, 0.0, 50.0];
    let result = validate_temperature(temp.view());
    assert!(result.is_ok(), "Should accept valid temperatures");
}

// =============================================================================
// compute_normalization Tests
// =============================================================================

#[test]
fn test_compute_normalization_positive_sum() {
    let weights = [1.0, 2.0, 3.0];
    let sum = compute_normalization(&weights).unwrap();
    assert!((sum - 6.0).abs() < 1e-12);
}

#[test]
fn test_compute_normalization_single_element() {
    let weights = [0.5];
    let sum = compute_normalization(&weights).unwrap();
    assert!((sum - 0.5).abs() < 1e-12);
}

#[test]
fn test_compute_normalization_zero_sum_rejected() {
    // Guards against a future refactor that makes beta configurable:
    // extreme negative beta with high elevations could underflow the sum
    // of exp(beta * dz) to zero, which would crash the downstream divide.
    // This test pins the explicit NumericalError return path.
    let weights = [0.0, 0.0, 0.0];
    let result = compute_normalization(&weights);
    assert!(matches!(
        result,
        Err(SnowError::NumericalError {
            context: "CemaNeige precipitation normalization",
            ..
        })
    ));
}

#[test]
fn test_compute_normalization_below_tolerance_rejected() {
    // A sum that is technically non-zero but below TOLERANCE (1e-10)
    // must still be rejected — otherwise downstream division produces
    // giant / NaN effective precipitation.
    let weights = [1e-12, 1e-12];
    let result = compute_normalization(&weights);
    assert!(matches!(result, Err(SnowError::NumericalError { .. })));
}
