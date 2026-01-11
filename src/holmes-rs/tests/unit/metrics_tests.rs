use approx::assert_relative_eq;
use holmes_rs::metrics::{
    calculate_kge, calculate_nse, calculate_rmse, validate_result,
    MetricsError,
};
use ndarray::array;
use proptest::prelude::*;

// =============================================================================
// RMSE Tests
// =============================================================================

#[test]
fn test_rmse_perfect_prediction() {
    let obs = array![1.0, 2.0, 3.0];
    let sim = array![1.0, 2.0, 3.0];
    let rmse = calculate_rmse(obs.view(), sim.view()).unwrap();
    assert_relative_eq!(rmse, 0.0, epsilon = 1e-10);
}

#[test]
fn test_rmse_known_value() {
    let obs = array![1.0, 2.0, 3.0, 4.0];
    let sim = array![1.1, 1.9, 3.2, 3.8];
    let rmse = calculate_rmse(obs.view(), sim.view()).unwrap();
    // Expected: sqrt((0.01 + 0.01 + 0.04 + 0.04) / 4) = sqrt(0.025) ≈ 0.158
    assert_relative_eq!(rmse, 0.158, epsilon = 0.01);
}

#[test]
fn test_rmse_non_negative() {
    let obs = array![1.0, 5.0, 10.0, 2.0];
    let sim = array![2.0, 4.0, 8.0, 3.0];
    let rmse = calculate_rmse(obs.view(), sim.view()).unwrap();
    assert!(rmse >= 0.0);
}

// =============================================================================
// NSE Tests
// =============================================================================

#[test]
fn test_nse_perfect_prediction() {
    let obs = array![1.0, 2.0, 3.0, 4.0, 5.0];
    let sim = array![1.0, 2.0, 3.0, 4.0, 5.0];
    let nse = calculate_nse(obs.view(), sim.view()).unwrap();
    assert_relative_eq!(nse, 1.0, epsilon = 1e-10);
}

#[test]
fn test_nse_mean_prediction() {
    let obs = array![1.0, 2.0, 3.0, 4.0, 5.0];
    let mean = 3.0;
    let sim = array![mean, mean, mean, mean, mean];
    let nse = calculate_nse(obs.view(), sim.view()).unwrap();
    assert_relative_eq!(nse, 0.0, epsilon = 1e-10);
}

#[test]
fn test_nse_upper_bound() {
    let obs = array![1.0, 5.0, 10.0, 2.0, 8.0];
    let sim = array![2.0, 4.0, 8.0, 3.0, 7.0];
    let nse = calculate_nse(obs.view(), sim.view()).unwrap();
    assert!(nse <= 1.0);
}

#[test]
fn test_nse_worse_than_mean() {
    let obs = array![1.0, 2.0, 3.0, 4.0, 5.0];
    // Simulation that is worse than just predicting the mean
    let sim = array![5.0, 4.0, 3.0, 2.0, 1.0];
    let nse = calculate_nse(obs.view(), sim.view()).unwrap();
    assert!(nse < 0.0);
}

// =============================================================================
// KGE Tests
// =============================================================================

#[test]
fn test_kge_perfect_prediction() {
    let obs = array![1.0, 2.0, 3.0, 4.0, 5.0];
    let sim = array![1.0, 2.0, 3.0, 4.0, 5.0];
    let kge = calculate_kge(obs.view(), sim.view()).unwrap();
    assert_relative_eq!(kge, 1.0, epsilon = 1e-10);
}

#[test]
fn test_kge_upper_bound() {
    let obs = array![1.0, 5.0, 10.0, 2.0, 8.0];
    let sim = array![2.0, 4.0, 8.0, 3.0, 7.0];
    let kge = calculate_kge(obs.view(), sim.view()).unwrap();
    assert!(kge <= 1.0);
}

#[test]
fn test_kge_scaled_simulation() {
    // When simulations are scaled versions of observations, KGE should reflect that
    let obs = array![1.0, 2.0, 3.0, 4.0, 5.0];
    let sim = array![2.0, 4.0, 6.0, 8.0, 10.0]; // 2x observations
    let kge = calculate_kge(obs.view(), sim.view()).unwrap();
    // Correlation should be 1.0, but alpha and beta won't be perfect
    assert!(kge < 1.0);
}

// =============================================================================
// Error Handling Tests
// =============================================================================

#[test]
fn test_length_mismatch() {
    let obs = array![1.0, 2.0, 3.0];
    let sim = array![1.0, 2.0];

    let result = calculate_rmse(obs.view(), sim.view());
    assert!(matches!(result, Err(MetricsError::LengthMismatch(3, 2))));

    let result = calculate_nse(obs.view(), sim.view());
    assert!(matches!(result, Err(MetricsError::LengthMismatch(3, 2))));

    let result = calculate_kge(obs.view(), sim.view());
    assert!(matches!(result, Err(MetricsError::LengthMismatch(3, 2))));
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_rmse_non_negative(
        obs in prop::collection::vec(-100.0f64..100.0, 2..50),
        sim in prop::collection::vec(-100.0f64..100.0, 2..50)
    ) {
        let len = obs.len().min(sim.len());
        let obs_arr = ndarray::Array1::from_vec(obs[..len].to_vec());
        let sim_arr = ndarray::Array1::from_vec(sim[..len].to_vec());
        let rmse = calculate_rmse(obs_arr.view(), sim_arr.view()).unwrap();
        prop_assert!(rmse >= 0.0);
    }

    #[test]
    fn prop_rmse_symmetric(
        values in prop::collection::vec(0.0f64..100.0, 2..50)
    ) {
        let len = values.len();
        let a = ndarray::Array1::from_vec(values[..len/2].to_vec());
        let b = ndarray::Array1::from_vec(values[len/2..len/2 + a.len()].to_vec());
        if a.len() == b.len() && !a.is_empty() {
            let rmse_ab = calculate_rmse(a.view(), b.view()).unwrap();
            let rmse_ba = calculate_rmse(b.view(), a.view()).unwrap();
            prop_assert!((rmse_ab - rmse_ba).abs() < 1e-10);
        }
    }

    #[test]
    fn prop_nse_upper_bound(
        obs in prop::collection::vec(1.0f64..100.0, 3..50),
        sim in prop::collection::vec(1.0f64..100.0, 3..50)
    ) {
        let len = obs.len().min(sim.len());
        let obs_arr = ndarray::Array1::from_vec(obs[..len].to_vec());
        let sim_arr = ndarray::Array1::from_vec(sim[..len].to_vec());
        let nse = calculate_nse(obs_arr.view(), sim_arr.view()).unwrap();
        prop_assert!(nse <= 1.0 + 1e-10);
    }

    #[test]
    fn prop_identical_nse_one(
        values in prop::collection::vec(1.0f64..100.0, 3..50)
    ) {
        let arr = ndarray::Array1::from_vec(values);
        let nse = calculate_nse(arr.view(), arr.view()).unwrap();
        prop_assert!((nse - 1.0).abs() < 1e-10);
    }

    #[test]
    fn prop_identical_kge_one(
        values in prop::collection::vec(1.0f64..100.0, 3..50)
    ) {
        let arr = ndarray::Array1::from_vec(values);
        let kge = calculate_kge(arr.view(), arr.view()).unwrap();
        prop_assert!((kge - 1.0).abs() < 1e-10);
    }

    #[test]
    fn prop_kge_upper_bound(
        obs in prop::collection::vec(1.0f64..100.0, 3..50),
        sim in prop::collection::vec(1.0f64..100.0, 3..50)
    ) {
        let len = obs.len().min(sim.len());
        let obs_arr = ndarray::Array1::from_vec(obs[..len].to_vec());
        let sim_arr = ndarray::Array1::from_vec(sim[..len].to_vec());
        let kge = calculate_kge(obs_arr.view(), sim_arr.view()).unwrap();
        prop_assert!(kge <= 1.0 + 1e-10);
    }
}

// =============================================================================
// Anti-Fragility Tests - Now enabled with proper error handling
// =============================================================================

#[test]
fn test_nse_constant_observations() {
    let obs = array![5.0, 5.0, 5.0, 5.0, 5.0];
    let sim = array![4.0, 5.0, 6.0, 5.0, 4.0];
    let result = calculate_nse(obs.view(), sim.view());
    // When observations are constant, should return ZeroVarianceNSE error
    assert!(
        matches!(result, Err(MetricsError::ZeroVarianceNSE)),
        "NSE should return ZeroVarianceNSE for constant observations"
    );
}

#[test]
fn test_kge_zero_std_observations() {
    let obs = array![5.0, 5.0, 5.0, 5.0, 5.0];
    let sim = array![4.0, 5.0, 6.0, 5.0, 4.0];
    let result = calculate_kge(obs.view(), sim.view());
    // Zero std in observations should return ZeroVarianceKGE error
    assert!(
        matches!(
            result,
            Err(MetricsError::ZeroVarianceKGE {
                component: "observations"
            })
        ),
        "KGE should return ZeroVarianceKGE for zero std observations"
    );
}

#[test]
fn test_kge_zero_std_simulations() {
    let obs = array![4.0, 5.0, 6.0, 5.0, 4.0];
    let sim = array![5.0, 5.0, 5.0, 5.0, 5.0];
    let result = calculate_kge(obs.view(), sim.view());
    // Zero std in simulations should return ZeroVarianceKGE error
    assert!(
        matches!(
            result,
            Err(MetricsError::ZeroVarianceKGE {
                component: "simulations"
            })
        ),
        "KGE should return ZeroVarianceKGE for zero std simulations"
    );
}

#[test]
fn test_kge_zero_mean_observations() {
    let obs = array![-2.0, -1.0, 0.0, 1.0, 2.0];
    let sim = array![1.0, 2.0, 3.0, 4.0, 5.0];
    let result = calculate_kge(obs.view(), sim.view());
    // Zero mean should return ZeroMeanKGE error
    assert!(
        matches!(result, Err(MetricsError::ZeroMeanKGE)),
        "KGE should return ZeroMeanKGE for zero mean observations"
    );
}

#[test]
fn test_metrics_nan_input_observations() {
    let obs = array![1.0, f64::NAN, 3.0];
    let sim = array![1.0, 2.0, 3.0];

    let result = calculate_rmse(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::NaNInInput {
                array_name: "observations",
                index: 1
            })
        ),
        "RMSE should reject NaN in observations"
    );

    let result = calculate_nse(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::NaNInInput {
                array_name: "observations",
                ..
            })
        ),
        "NSE should reject NaN input"
    );

    let result = calculate_kge(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::NaNInInput {
                array_name: "observations",
                ..
            })
        ),
        "KGE should reject NaN input"
    );
}

#[test]
fn test_metrics_nan_input_simulations() {
    let obs = array![1.0, 2.0, 3.0];
    let sim = array![1.0, f64::NAN, 3.0];

    let result = calculate_rmse(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::NaNInInput {
                array_name: "simulations",
                index: 1
            })
        ),
        "RMSE should reject NaN in simulations"
    );
}

#[test]
fn test_metrics_infinity_input_observations() {
    let obs = array![1.0, f64::INFINITY, 3.0];
    let sim = array![1.0, 2.0, 3.0];

    let result = calculate_rmse(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::InfinityInInput {
                array_name: "observations",
                ..
            })
        ),
        "RMSE should reject Infinity in observations"
    );

    let result = calculate_nse(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::InfinityInInput {
                array_name: "observations",
                ..
            })
        ),
        "NSE should reject Infinity in observations"
    );

    let result = calculate_kge(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::InfinityInInput {
                array_name: "observations",
                ..
            })
        ),
        "KGE should reject Infinity in observations"
    );
}

#[test]
fn test_metrics_infinity_input_simulations() {
    let obs = array![1.0, 2.0, 3.0];
    let sim = array![1.0, f64::INFINITY, 3.0];

    let result = calculate_rmse(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::InfinityInInput {
                array_name: "simulations",
                index: 1,
                ..
            })
        ),
        "RMSE should reject Infinity in simulations"
    );

    let result = calculate_nse(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::InfinityInInput {
                array_name: "simulations",
                ..
            })
        ),
        "NSE should reject Infinity in simulations"
    );

    let result = calculate_kge(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::InfinityInInput {
                array_name: "simulations",
                ..
            })
        ),
        "KGE should reject Infinity in simulations"
    );
}

#[test]
fn test_metrics_neg_infinity_input() {
    let obs = array![1.0, f64::NEG_INFINITY, 3.0];
    let sim = array![1.0, 2.0, 3.0];

    let result = calculate_rmse(obs.view(), sim.view());
    assert!(
        matches!(
            result,
            Err(MetricsError::InfinityInInput {
                array_name: "observations",
                ..
            })
        ),
        "RMSE should reject negative infinity"
    );
}

#[test]
fn test_metrics_empty_arrays() {
    let obs: ndarray::Array1<f64> = array![];
    let sim: ndarray::Array1<f64> = array![];

    let result = calculate_rmse(obs.view(), sim.view());
    assert!(
        matches!(result, Err(MetricsError::EmptyArrays)),
        "RMSE should reject empty arrays"
    );

    let result = calculate_nse(obs.view(), sim.view());
    assert!(
        matches!(result, Err(MetricsError::EmptyArrays)),
        "NSE should reject empty arrays"
    );

    let result = calculate_kge(obs.view(), sim.view());
    assert!(
        matches!(result, Err(MetricsError::EmptyArrays)),
        "KGE should reject empty arrays"
    );
}

// =============================================================================
// Direct Utility Function Tests
// =============================================================================

#[test]
fn test_validate_result_nan() {
    let result =
        validate_result(f64::NAN, "test context", "detail".to_string());
    assert!(
        matches!(
            result,
            Err(MetricsError::NumericalError {
                context: "test context",
                ..
            })
        ),
        "Should reject NaN result"
    );
}

#[test]
fn test_validate_result_infinity() {
    let result =
        validate_result(f64::INFINITY, "test", "infinity detail".to_string());
    assert!(
        matches!(
            result,
            Err(MetricsError::NumericalError {
                context: "test",
                ..
            })
        ),
        "Should reject Infinity result"
    );
}

#[test]
fn test_validate_result_neg_infinity() {
    let result =
        validate_result(f64::NEG_INFINITY, "neg inf test", "neg".to_string());
    assert!(
        matches!(result, Err(MetricsError::NumericalError { .. })),
        "Should reject negative infinity result"
    );
}

#[test]
fn test_validate_result_valid() {
    let result = validate_result(42.0, "valid test", "detail".to_string());
    assert!(result.is_ok(), "Should accept valid finite value");
    assert_eq!(result.unwrap(), 42.0);
}

#[test]
fn test_validate_result_zero() {
    let result = validate_result(0.0, "zero test", "detail".to_string());
    assert!(result.is_ok(), "Should accept zero");
    assert_eq!(result.unwrap(), 0.0);
}

#[test]
fn test_validate_result_negative() {
    let result =
        validate_result(-100.0, "negative test", "detail".to_string());
    assert!(result.is_ok(), "Should accept negative finite values");
    assert_eq!(result.unwrap(), -100.0);
}
