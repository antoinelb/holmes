use crate::helpers;
use holmes_rs::pet::oudin::simulate;
use holmes_rs::pet::utils::{
    validate_day_of_year, validate_latitude, validate_output,
    validate_temperature,
};
use holmes_rs::pet::PetError;
use ndarray::{array, Array1};
use proptest::prelude::*;

// =============================================================================
// Basic Functionality Tests
// =============================================================================

#[test]
fn test_oudin_summer_midlat() {
    // Mid-latitude (45°N), summer day (day 180), warm temperature
    let temp = array![25.0];
    let doy = array![180_usize];
    let latitude = 45.0;

    let pet = simulate(temp.view(), doy.view(), latitude).unwrap();

    assert_eq!(pet.len(), 1);
    // Summer PET at mid-latitude with 25°C should be reasonable (2-6 mm/day)
    assert!(
        pet[0] >= 2.0 && pet[0] <= 6.0,
        "Summer PET at 45°N, 25°C should be between 2-6 mm/day, got {}",
        pet[0]
    );
}

#[test]
fn test_oudin_winter() {
    // Winter conditions: cold temperature
    let temp = array![-10.0, -5.0, 0.0, 2.0, 5.0];
    let doy = array![15_usize, 15, 15, 15, 15]; // Mid-January
    let latitude = 45.0;

    let pet = simulate(temp.view(), doy.view(), latitude).unwrap();

    // PET should be clamped to >= 0
    assert!(
        pet.iter().all(|&p| p >= 0.0),
        "PET should never be negative"
    );

    // Cold temps should produce low or zero PET
    assert!(
        pet[0] < 1.0,
        "PET at -10°C should be very low, got {}",
        pet[0]
    );
}

#[test]
fn test_oudin_equator() {
    // Equatorial latitude (0°)
    let temp = Array1::from_elem(365, 25.0);
    let doy = helpers::generate_doy(1, 365);
    let latitude = 0.0;

    let pet = simulate(temp.view(), doy.view(), latitude).unwrap();

    assert_eq!(pet.len(), 365);
    // At equator, PET should be relatively consistent throughout the year
    let mean = pet.mean().unwrap();
    let std = (pet.mapv(|x| (x - mean).powi(2)).mean().unwrap()).sqrt();

    // Standard deviation should be low relative to mean for equatorial PET
    assert!(
        std / mean < 0.3,
        "Equatorial PET should be relatively constant"
    );
}

#[test]
fn test_oudin_full_year() {
    // Full year at mid-latitude
    let temp = helpers::generate_temperature(365, 10.0, 15.0, 2.0, 42);
    let doy = helpers::generate_doy(1, 365);
    let latitude = 45.0;

    let pet = simulate(temp.view(), doy.view(), latitude).unwrap();

    assert_eq!(pet.len(), 365);
    assert!(
        pet.iter().all(|&p| p >= 0.0),
        "All PET should be non-negative"
    );
    assert!(
        pet.iter().all(|&p| p.is_finite()),
        "All PET should be finite"
    );

    // Should show seasonal pattern: higher in summer (days ~150-200)
    let winter_mean = pet.slice(ndarray::s![0..60]).mean().unwrap();
    let summer_mean = pet.slice(ndarray::s![150..210]).mean().unwrap();
    assert!(
        summer_mean > winter_mean,
        "Summer PET should be higher than winter"
    );
}

// =============================================================================
// Error Handling Tests
// =============================================================================

#[test]
fn test_oudin_length_mismatch() {
    let temp = array![20.0, 22.0, 24.0];
    let doy = array![180_usize, 181]; // Length mismatch

    let result = simulate(temp.view(), doy.view(), 45.0);
    assert!(matches!(result, Err(PetError::LengthMismatch(3, 2))));
}

#[test]
fn test_oudin_empty_temperature() {
    let temp: Array1<f64> = array![];
    let doy: Array1<usize> = array![];

    let result = simulate(temp.view(), doy.view(), 45.0);
    assert!(
        matches!(
            result,
            Err(PetError::EmptyInput {
                name: "temperature"
            })
        ),
        "Should reject empty temperature array"
    );
}

#[test]
fn test_oudin_nan_in_temperature() {
    let temp = array![20.0, f64::NAN, 22.0];
    let doy = array![180_usize, 181, 182];

    let result = simulate(temp.view(), doy.view(), 45.0);
    assert!(
        matches!(
            result,
            Err(PetError::NonFiniteInput {
                name: "temperature",
                index: 1,
                ..
            })
        ),
        "Should reject NaN in temperature"
    );
}

#[test]
fn test_oudin_infinity_in_temperature() {
    let temp = array![20.0, f64::INFINITY, 22.0];
    let doy = array![180_usize, 181, 182];

    let result = simulate(temp.view(), doy.view(), 45.0);
    assert!(
        matches!(
            result,
            Err(PetError::NonFiniteInput {
                name: "temperature",
                ..
            })
        ),
        "Should reject infinity in temperature"
    );
}

#[test]
fn test_oudin_temperature_too_low() {
    let temp = array![20.0, -150.0, 22.0]; // -150 is below -100 min
    let doy = array![180_usize, 181, 182];

    let result = simulate(temp.view(), doy.view(), 45.0);
    assert!(
        matches!(
            result,
            Err(PetError::TemperatureOutOfRange {
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
fn test_oudin_temperature_too_high() {
    let temp = array![20.0, 150.0, 22.0]; // 150 is above 100 max
    let doy = array![180_usize, 181, 182];

    let result = simulate(temp.view(), doy.view(), 45.0);
    assert!(
        matches!(
            result,
            Err(PetError::TemperatureOutOfRange {
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
fn test_oudin_invalid_day_of_year_zero() {
    let temp = array![20.0, 22.0, 24.0];
    let doy = array![180_usize, 0, 182]; // 0 is invalid

    let result = simulate(temp.view(), doy.view(), 45.0);
    assert!(
        matches!(
            result,
            Err(PetError::InvalidDayOfYear { index: 1, value: 0 })
        ),
        "Should reject day of year 0"
    );
}

#[test]
fn test_oudin_invalid_day_of_year_367() {
    let temp = array![20.0, 22.0, 24.0];
    let doy = array![180_usize, 367, 182]; // 367 is invalid

    let result = simulate(temp.view(), doy.view(), 45.0);
    assert!(
        matches!(
            result,
            Err(PetError::InvalidDayOfYear {
                index: 1,
                value: 367
            })
        ),
        "Should reject day of year > 366"
    );
}

#[test]
fn test_oudin_latitude_too_low() {
    let temp = array![20.0];
    let doy = array![180_usize];

    let result = simulate(temp.view(), doy.view(), -95.0); // below -90
    assert!(
        matches!(
            result,
            Err(PetError::LatitudeOutOfRange {
                min: -90.0,
                max: 90.0,
                ..
            })
        ),
        "Should reject latitude below -90"
    );
}

#[test]
fn test_oudin_latitude_too_high() {
    let temp = array![20.0];
    let doy = array![180_usize];

    let result = simulate(temp.view(), doy.view(), 95.0); // above 90
    assert!(
        matches!(
            result,
            Err(PetError::LatitudeOutOfRange {
                min: -90.0,
                max: 90.0,
                ..
            })
        ),
        "Should reject latitude above 90"
    );
}

#[test]
fn test_oudin_latitude_nan() {
    let temp = array![20.0];
    let doy = array![180_usize];

    let result = simulate(temp.view(), doy.view(), f64::NAN);
    assert!(
        matches!(result, Err(PetError::LatitudeOutOfRange { .. })),
        "Should reject NaN latitude"
    );
}

// =============================================================================
// Latitude Tests
// =============================================================================

#[test]
fn test_oudin_various_latitudes() {
    let temp = array![20.0];
    let doy = array![180_usize]; // Summer solstice

    for lat in [0.0, 15.0, 30.0, 45.0, 60.0] {
        let pet = simulate(temp.view(), doy.view(), lat).unwrap();
        assert!(
            pet[0].is_finite() && pet[0] >= 0.0,
            "PET at latitude {} should be valid",
            lat
        );
    }
}

#[test]
fn test_oudin_southern_hemisphere() {
    // Southern hemisphere should have reversed seasons
    let temp = array![25.0];
    let doy_summer = array![15_usize]; // January (summer in S. hemisphere)
    let doy_winter = array![180_usize]; // July (winter in S. hemisphere)
    let latitude = -35.0;

    let pet_summer =
        simulate(temp.view(), doy_summer.view(), latitude).unwrap();
    let pet_winter =
        simulate(temp.view(), doy_winter.view(), latitude).unwrap();

    // Both should be valid
    assert!(pet_summer[0].is_finite() && pet_summer[0] >= 0.0);
    assert!(pet_winter[0].is_finite() && pet_winter[0] >= 0.0);
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_pet_nonnegative(
        temp in -30.0f64..50.0,
        doy in 1usize..365,
        lat in -60.0f64..60.0
    ) {
        let temp_arr = array![temp];
        let doy_arr = array![doy];

        let pet = simulate(temp_arr.view(), doy_arr.view(), lat).unwrap();
        prop_assert!(pet[0] >= 0.0, "PET should be non-negative");
    }

    #[test]
    fn prop_pet_finite(
        temp in -20.0f64..40.0,
        doy in 1usize..365,
        lat in -50.0f64..50.0
    ) {
        let temp_arr = array![temp];
        let doy_arr = array![doy];

        let pet = simulate(temp_arr.view(), doy_arr.view(), lat).unwrap();
        prop_assert!(pet[0].is_finite(), "PET should be finite");
    }

    #[test]
    fn prop_higher_temp_more_pet(
        doy in 1usize..365,
        lat in -45.0f64..45.0
    ) {
        let temp_low = array![10.0];
        let temp_high = array![30.0];
        let doy_arr = array![doy];

        let pet_low = simulate(temp_low.view(), doy_arr.view(), lat).unwrap();
        let pet_high = simulate(temp_high.view(), doy_arr.view(), lat).unwrap();

        // Higher temperature should generally produce higher PET
        // (allowing some tolerance for edge cases)
        prop_assert!(pet_high[0] >= pet_low[0] - 0.1);
    }
}

// =============================================================================
// Anti-Fragility Tests (expected to fail with current implementation)
// =============================================================================

#[test]
#[ignore = "R5-NUM-05: Lambda approaches zero at extreme temperatures"]
fn test_oudin_extreme_temperature() {
    // Very high temperature: lambda = 2.501 - 0.002361 * T approaches 0
    // At T ≈ 1059°C, lambda = 0, causing division issues
    let temp = array![100.0, 500.0, 1000.0];
    let doy = array![180_usize, 180, 180];
    let latitude = 45.0;

    let pet = simulate(temp.view(), doy.view(), latitude).unwrap();
    assert!(
        pet.iter().all(|&p| p.is_finite()),
        "PET should handle extreme temperatures"
    );
}

#[test]
#[ignore = "R5-NUM-05: tan(latitude) approaches infinity near poles"]
fn test_oudin_extreme_latitude() {
    // Near polar latitudes cause issues with tan() in sunset hour angle calculation
    let temp = array![10.0];
    let doy = array![180_usize];

    // 89° should still work but may have numerical issues
    let result_high = simulate(temp.view(), doy.view(), 89.0);
    if let Ok(pet) = result_high {
        assert!(pet[0].is_finite(), "PET at 89°N should be finite");
    }

    // 90° is problematic (tan(90°) = ∞)
    let result_pole = simulate(temp.view(), doy.view(), 90.0);
    if let Ok(pet) = result_pole {
        assert!(
            pet[0].is_finite(),
            "PET at 90°N should be handled gracefully"
        );
    }
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
            Err(PetError::EmptyInput {
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
            Err(PetError::NumericalError {
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
            Err(PetError::NumericalError {
                context: "test context",
                ..
            })
        ),
        "Should reject Infinity in output"
    );
}

#[test]
fn test_validate_output_neg_infinity() {
    let arr = array![f64::NEG_INFINITY, 2.0, 3.0];
    let result = validate_output(arr.view(), "test");
    assert!(
        matches!(result, Err(PetError::NumericalError { .. })),
        "Should reject negative infinity in output"
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

#[test]
fn test_validate_latitude_valid() {
    assert!(validate_latitude(0.0).is_ok());
    assert!(validate_latitude(-90.0).is_ok());
    assert!(validate_latitude(90.0).is_ok());
    assert!(validate_latitude(45.0).is_ok());
}

#[test]
fn test_validate_latitude_infinity() {
    let result = validate_latitude(f64::INFINITY);
    assert!(
        matches!(result, Err(PetError::LatitudeOutOfRange { .. })),
        "Should reject Infinity latitude"
    );
}
