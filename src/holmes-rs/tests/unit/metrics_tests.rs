use approx::assert_relative_eq;
use holmes_rs::metrics::{
    calculate_kge, calculate_nse, calculate_rmse, MetricsError,
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
// Anti-Fragility Tests (expected to fail with current implementation)
// These tests document known numerical issues
// =============================================================================

#[test]
#[ignore = "R5-NUM-01: NSE division by zero when observations are constant"]
fn test_nse_constant_observations() {
    let obs = array![5.0, 5.0, 5.0, 5.0, 5.0];
    let sim = array![4.0, 5.0, 6.0, 5.0, 4.0];
    let nse = calculate_nse(obs.view(), sim.view()).unwrap();
    // When observations are constant, denominator is 0, causing division by zero
    // Proper implementation should return an error or handle gracefully
    assert!(nse.is_finite(), "NSE should handle constant observations");
}

#[test]
#[ignore = "R5-NUM-02: KGE NaN when observation std is zero"]
fn test_kge_zero_std_observations() {
    let obs = array![5.0, 5.0, 5.0, 5.0, 5.0];
    let sim = array![4.0, 5.0, 6.0, 5.0, 4.0];
    let kge = calculate_kge(obs.view(), sim.view()).unwrap();
    // Zero std in observations causes 0/0 in correlation calculation
    assert!(kge.is_finite(), "KGE should handle zero std observations");
}

#[test]
#[ignore = "R5-NUM-03: KGE NaN when simulation std is zero"]
fn test_kge_zero_std_simulations() {
    let obs = array![4.0, 5.0, 6.0, 5.0, 4.0];
    let sim = array![5.0, 5.0, 5.0, 5.0, 5.0];
    let kge = calculate_kge(obs.view(), sim.view()).unwrap();
    // Zero std in simulations causes NaN in alpha = sim_std / obs_std
    assert!(kge.is_finite(), "KGE should handle zero std simulations");
}

#[test]
#[ignore = "R5-NUM-04: KGE infinity when observation mean is zero"]
fn test_kge_zero_mean_observations() {
    let obs = array![-2.0, -1.0, 0.0, 1.0, 2.0];
    let sim = array![1.0, 2.0, 3.0, 4.0, 5.0];
    let kge = calculate_kge(obs.view(), sim.view()).unwrap();
    // Zero mean causes infinity in beta = sim_mean / obs_mean
    assert!(kge.is_finite(), "KGE should handle zero mean observations");
}

#[test]
#[ignore = "R1-ERR-01: NaN input propagates silently"]
fn test_metrics_nan_input() {
    let obs = array![1.0, f64::NAN, 3.0];
    let sim = array![1.0, 2.0, 3.0];

    let rmse = calculate_rmse(obs.view(), sim.view()).unwrap();
    assert!(rmse.is_finite(), "RMSE should reject NaN input");

    let nse = calculate_nse(obs.view(), sim.view()).unwrap();
    assert!(nse.is_finite(), "NSE should reject NaN input");

    let kge = calculate_kge(obs.view(), sim.view()).unwrap();
    assert!(kge.is_finite(), "KGE should reject NaN input");
}

#[test]
#[ignore = "R1-ERR-01: Infinity input propagates silently"]
fn test_metrics_infinity_input() {
    let obs = array![1.0, f64::INFINITY, 3.0];
    let sim = array![1.0, 2.0, 3.0];

    let rmse = calculate_rmse(obs.view(), sim.view()).unwrap();
    assert!(rmse.is_finite(), "RMSE should reject Infinity input");

    let nse = calculate_nse(obs.view(), sim.view()).unwrap();
    assert!(nse.is_finite(), "NSE should reject Infinity input");

    let kge = calculate_kge(obs.view(), sim.view()).unwrap();
    assert!(kge.is_finite(), "KGE should reject Infinity input");
}
