use crate::helpers;
use holmes_rs::calibration::utils::{
    CalibrationError, Objective, Transformation,
};
use holmes_rs::hydro::{self, HydroError};
use holmes_rs::snow;
use std::str::FromStr;

// =============================================================================
// Objective Enum Tests
// =============================================================================

#[test]
fn test_objective_from_str_rmse() {
    let obj = Objective::from_str("rmse").unwrap();
    assert!(matches!(obj, Objective::Rmse));

    // Case insensitive
    let obj = Objective::from_str("RMSE").unwrap();
    assert!(matches!(obj, Objective::Rmse));

    let obj = Objective::from_str("Rmse").unwrap();
    assert!(matches!(obj, Objective::Rmse));
}

#[test]
fn test_objective_from_str_nse() {
    let obj = Objective::from_str("nse").unwrap();
    assert!(matches!(obj, Objective::Nse));

    let obj = Objective::from_str("NSE").unwrap();
    assert!(matches!(obj, Objective::Nse));
}

#[test]
fn test_objective_from_str_kge() {
    let obj = Objective::from_str("kge").unwrap();
    assert!(matches!(obj, Objective::Kge));

    let obj = Objective::from_str("KGE").unwrap();
    assert!(matches!(obj, Objective::Kge));
}

#[test]
fn test_objective_from_str_invalid() {
    let result = Objective::from_str("invalid");
    assert!(result.is_err());

    let result = Objective::from_str("r2");
    assert!(result.is_err());
}

// =============================================================================
// Transformation Enum Tests
// =============================================================================

#[test]
fn test_transformation_from_str_log() {
    let trans = Transformation::from_str("log").unwrap();
    assert!(matches!(trans, Transformation::Log));

    let trans = Transformation::from_str("LOG").unwrap();
    assert!(matches!(trans, Transformation::Log));
}

#[test]
fn test_transformation_from_str_sqrt() {
    let trans = Transformation::from_str("sqrt").unwrap();
    assert!(matches!(trans, Transformation::Sqrt));

    let trans = Transformation::from_str("SQRT").unwrap();
    assert!(matches!(trans, Transformation::Sqrt));
}

#[test]
fn test_transformation_from_str_none() {
    let trans = Transformation::from_str("none").unwrap();
    assert!(matches!(trans, Transformation::None));

    let trans = Transformation::from_str("NONE").unwrap();
    assert!(matches!(trans, Transformation::None));
}

#[test]
fn test_transformation_from_str_invalid() {
    let result = Transformation::from_str("invalid");
    assert!(result.is_err());

    let result = Transformation::from_str("box-cox");
    assert!(result.is_err());
}

// =============================================================================
// Model Registry Tests
// =============================================================================

#[test]
fn test_hydro_get_model_gr4j() {
    let result = hydro::get_model("gr4j");
    assert!(result.is_ok());

    let (init_fn, _simulate_fn) = result.unwrap();

    // Test init returns proper shapes
    let (defaults, bounds) = init_fn();
    assert_eq!(defaults.len(), 4);
    assert_eq!(bounds.shape(), &[4, 2]);
}

#[test]
fn test_hydro_get_model_bucket() {
    let result = hydro::get_model("bucket");
    assert!(result.is_ok());

    let (init_fn, _) = result.unwrap();
    let (defaults, bounds) = init_fn();
    assert_eq!(defaults.len(), 6);
    assert_eq!(bounds.shape(), &[6, 2]);
}

#[test]
fn test_hydro_get_model_invalid() {
    let result = hydro::get_model("invalid_model");
    assert!(matches!(result, Err(HydroError::WrongModel(_))));
}

#[test]
fn test_snow_get_model_cemaneige() {
    let result = snow::get_model("cemaneige");
    assert!(result.is_ok());

    let (init_fn, _) = result.unwrap();
    let (defaults, bounds) = init_fn();
    assert_eq!(defaults.len(), 3);
    assert_eq!(bounds.shape(), &[3, 2]);
}

#[test]
fn test_snow_get_model_invalid() {
    let result = snow::get_model("invalid_model");
    assert!(result.is_err());
}

// =============================================================================
// Compose Simulate Tests
// =============================================================================

#[test]
fn test_compose_simulate_hydro_only() {
    use holmes_rs::calibration::utils::compose_simulate;
    use ndarray::array;

    let (_, hydro_simulate) = hydro::get_model("gr4j").unwrap();
    let simulate = compose_simulate(None, hydro_simulate, 0);

    // Prepare test data
    let params = array![300.0, 0.5, 100.0, 2.0]; // GR4J params
    let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(50, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, 50);

    // No snow model, so snow params are None
    let result = simulate(
        params.view(),
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
    );

    assert!(result.is_ok());
    let streamflow = result.unwrap();
    assert_eq!(streamflow.len(), 50);
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_compose_simulate_with_snow() {
    use holmes_rs::calibration::utils::compose_simulate;
    use ndarray::array;

    let (_, snow_simulate) = snow::get_model("cemaneige").unwrap();
    let (_, hydro_simulate) = hydro::get_model("gr4j").unwrap();
    let simulate = compose_simulate(Some(snow_simulate), hydro_simulate, 3);

    // Combined params: 3 snow + 4 hydro = 7 total
    let params = array![0.5, 5.0, 350.0, 300.0, 0.5, 100.0, 2.0];
    let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
    let temp = helpers::generate_temperature(50, 5.0, 15.0, 2.0, 43);
    let pet = helpers::generate_pet(50, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, 50);
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

    // Snow model requires temperature, elevation_bands, and median_elevation
    let result = simulate(
        params.view(),
        precip.view(),
        Some(temp.view()),
        pet.view(),
        doy.view(),
        Some(elevation_layers.view()),
        Some(median_elevation),
    );

    assert!(result.is_ok());
    let streamflow = result.unwrap();
    assert_eq!(streamflow.len(), 50);
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

// =============================================================================
// Check Lengths Tests
// =============================================================================

#[test]
fn test_check_lengths_matching() {
    use holmes_rs::calibration::utils::check_lengths;
    use ndarray::Array1;

    let precip = Array1::from_elem(100, 5.0);
    let temp = Array1::from_elem(100, 10.0);
    let pet = Array1::from_elem(100, 3.0);
    let doy = Array1::from_elem(100, 180_usize);

    let result = check_lengths(
        precip.view(),
        Some(temp.view()),
        pet.view(),
        doy.view(),
    );
    assert!(result.is_ok());
}

#[test]
fn test_check_lengths_matching_no_temp() {
    use holmes_rs::calibration::utils::check_lengths;
    use ndarray::Array1;

    let precip = Array1::from_elem(100, 5.0);
    let pet = Array1::from_elem(100, 3.0);
    let doy = Array1::from_elem(100, 180_usize);

    // When temperature is None, lengths should still match
    let result = check_lengths(precip.view(), None, pet.view(), doy.view());
    assert!(result.is_ok());
}

#[test]
fn test_check_lengths_mismatch() {
    use holmes_rs::calibration::utils::check_lengths;
    use ndarray::Array1;

    let precip = Array1::from_elem(100, 5.0);
    let temp = Array1::from_elem(100, 10.0);
    let pet = Array1::from_elem(50, 3.0); // Different length
    let doy = Array1::from_elem(100, 180_usize);

    let result = check_lengths(
        precip.view(),
        Some(temp.view()),
        pet.view(),
        doy.view(),
    );
    assert!(matches!(
        result,
        Err(CalibrationError::LengthMismatch(_, _, _, _))
    ));
}

// =============================================================================
// Missing Snow Params Tests
// =============================================================================

#[test]
fn test_compose_simulate_snow_missing_temperature() {
    use holmes_rs::calibration::utils::compose_simulate;
    use ndarray::array;

    let (_, snow_simulate) = snow::get_model("cemaneige").unwrap();
    let (_, hydro_simulate) = hydro::get_model("gr4j").unwrap();
    let simulate = compose_simulate(Some(snow_simulate), hydro_simulate, 3);

    let params = array![0.5, 5.0, 350.0, 300.0, 0.5, 100.0, 2.0];
    let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(50, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, 50);
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

    // Snow model configured but temperature is None - should fail
    let result = simulate(
        params.view(),
        precip.view(),
        None, // Missing temperature
        pet.view(),
        doy.view(),
        Some(elevation_layers.view()),
        Some(median_elevation),
    );

    assert!(matches!(result, Err(CalibrationError::MissingSnowParams)));
}

#[test]
fn test_compose_simulate_snow_missing_elevation_bands() {
    use holmes_rs::calibration::utils::compose_simulate;
    use ndarray::array;

    let (_, snow_simulate) = snow::get_model("cemaneige").unwrap();
    let (_, hydro_simulate) = hydro::get_model("gr4j").unwrap();
    let simulate = compose_simulate(Some(snow_simulate), hydro_simulate, 3);

    let params = array![0.5, 5.0, 350.0, 300.0, 0.5, 100.0, 2.0];
    let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
    let temp = helpers::generate_temperature(50, 5.0, 15.0, 2.0, 43);
    let pet = helpers::generate_pet(50, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, 50);
    let median_elevation = 1000.0;

    // Snow model configured but elevation_bands is None - should fail
    let result = simulate(
        params.view(),
        precip.view(),
        Some(temp.view()),
        pet.view(),
        doy.view(),
        None, // Missing elevation_bands
        Some(median_elevation),
    );

    assert!(matches!(result, Err(CalibrationError::MissingSnowParams)));
}

#[test]
fn test_compose_simulate_snow_missing_median_elevation() {
    use holmes_rs::calibration::utils::compose_simulate;
    use ndarray::array;

    let (_, snow_simulate) = snow::get_model("cemaneige").unwrap();
    let (_, hydro_simulate) = hydro::get_model("gr4j").unwrap();
    let simulate = compose_simulate(Some(snow_simulate), hydro_simulate, 3);

    let params = array![0.5, 5.0, 350.0, 300.0, 0.5, 100.0, 2.0];
    let precip = helpers::generate_precipitation(50, 5.0, 0.3, 42);
    let temp = helpers::generate_temperature(50, 5.0, 15.0, 2.0, 43);
    let pet = helpers::generate_pet(50, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, 50);
    let elevation_layers = array![1000.0];

    // Snow model configured but median_elevation is None - should fail
    let result = simulate(
        params.view(),
        precip.view(),
        Some(temp.view()),
        pet.view(),
        doy.view(),
        Some(elevation_layers.view()),
        None, // Missing median_elevation
    );

    assert!(matches!(result, Err(CalibrationError::MissingSnowParams)));
}

// =============================================================================
// Error Conversion Tests
// =============================================================================

#[test]
fn test_calibration_error_from_hydro() {
    let hydro_err = HydroError::ParamsMismatch(4, 3);
    let calib_err: CalibrationError = hydro_err.into();
    assert!(matches!(calib_err, CalibrationError::Hydro(_)));
}

#[test]
fn test_calibration_error_from_snow() {
    use holmes_rs::snow::SnowError;
    let snow_err = SnowError::ParamsMismatch(3, 2);
    let calib_err: CalibrationError = snow_err.into();
    assert!(matches!(calib_err, CalibrationError::Snow(_)));
}

#[test]
fn test_calibration_error_from_metrics() {
    use holmes_rs::metrics::MetricsError;
    let metrics_err = MetricsError::LengthMismatch(100, 50);
    let calib_err: CalibrationError = metrics_err.into();
    assert!(matches!(calib_err, CalibrationError::Metrics(_)));
}
