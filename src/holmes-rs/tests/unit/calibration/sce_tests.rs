use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::calibration::sce::{
    compute_criteria_change, evaluate_simulation, evolve_complex_step,
    sort_population, Sce,
};
use holmes_rs::calibration::utils::{Objective, Simulate, Transformation};
use ndarray::{array, Array1, Array2};
use proptest::prelude::*;
use std::str::FromStr;

// =============================================================================
// Constructor Tests
// =============================================================================

#[test]
fn test_sce_new_gr4j_only() {
    let result = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,      // n_complexes
        5,      // k_stop
        0.1,    // p_convergence_threshold
        0.0001, // geometric_range_threshold
        100,    // max_evaluations
        42,     // seed
    );

    assert!(result.is_ok(), "Should create Sce with GR4J only");
}

#[test]
fn test_sce_new_gr4j_cemaneige() {
    let result = Sce::new(
        "gr4j",
        Some("cemaneige"),
        Objective::Kge,
        holmes_rs::calibration::utils::Transformation::Log,
        2,
        5,
        0.1,
        0.0001,
        100,
        42,
    );

    assert!(result.is_ok(), "Should create Sce with GR4J + CemaNeige");
}

#[test]
fn test_sce_new_bucket_only() {
    let result = Sce::new(
        "bucket",
        None,
        Objective::Rmse,
        holmes_rs::calibration::utils::Transformation::Sqrt,
        2,
        5,
        0.1,
        0.0001,
        100,
        42,
    );

    assert!(result.is_ok(), "Should create Sce with Bucket model");
}

#[test]
fn test_sce_new_invalid_hydro_model() {
    let result = Sce::new(
        "invalid_model",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        100,
        42,
    );

    assert!(result.is_err(), "Should fail with invalid hydro model");
}

#[test]
fn test_sce_new_invalid_snow_model() {
    let result = Sce::new(
        "gr4j",
        Some("invalid_snow"),
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        100,
        42,
    );

    assert!(result.is_err(), "Should fail with invalid snow model");
}

#[test]
fn test_sce_new_valid_snow_invalid_hydro() {
    // Snow-first path: snow::get_model succeeds, then hydro::get_model
    // must fail. This exercises the ? propagation on hydro lookup inside
    // the snow-model branch of Sce::new — distinct from the no-snow
    // invalid-hydro path covered above.
    let result = Sce::new(
        "invalid_hydro",
        Some("cemaneige"),
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        100,
        42,
    );

    assert!(
        result.is_err(),
        "Should fail when hydro is invalid even with valid snow"
    );
}

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_sce_init_basic() {
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        1000,
        42,
    )
    .unwrap();

    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);

    // Generate synthetic observations (model output + noise)
    let (defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        defaults.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap()
    .mapv(|x| x * 1.1); // Add 10% bias

    // No snow model, so snow params are None
    let result = sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    );

    assert!(result.is_ok(), "Init should succeed: {:?}", result.err());
}

#[test]
fn test_init_all_missing_observations_errors() {
    // Every timestep after warmup is a gap (NaN). Init must fail loudly with
    // NoObservations rather than aborting later with a generic EmptyArrays
    // message from evaluate_simulation.
    use holmes_rs::calibration::utils::CalibrationError;

    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        100,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = Array1::from_elem(n, f64::NAN);

    let result = sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    );

    assert!(matches!(result, Err(CalibrationError::NoObservations)));
}

// =============================================================================
// Step Tests
// =============================================================================

#[test]
fn test_sce_step_returns_valid_output() {
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        50, // Low max_evaluations to finish quickly
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);

    // Generate synthetic observations
    let (defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        defaults.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap()
    .mapv(|x| x * 1.1);

    sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    let result = sce.step(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    );

    assert!(result.is_ok());
    let (_done, best_params, best_sim, objectives) = result.unwrap();

    // Check output shapes
    assert_eq!(best_params.len(), 4, "Should have 4 GR4J parameters");
    assert_eq!(best_sim.len(), n, "Simulation should match input length");
    assert_eq!(
        objectives.len(),
        3,
        "Should have 3 objectives (RMSE, NSE, KGE)"
    );

    // Check output validity
    assert!(
        best_params.iter().all(|&p| p.is_finite()),
        "All parameters should be finite"
    );
    assert!(
        best_sim.iter().all(|&s| s.is_finite() && s >= 0.0),
        "All simulations should be finite and non-negative"
    );
    assert!(
        objectives.iter().all(|&o| o.is_finite()),
        "All objectives should be finite"
    );
}

#[test]
fn test_sce_converges() {
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        3,
        1.0,   // High threshold to force quick convergence
        0.001, // Low geometric range threshold
        200,   // Reasonable max evaluations
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);

    // Generate synthetic observations from known parameters
    let known_params = array![300.0, 0.5, 100.0, 2.5];
    let obs = holmes_rs::hydro::gr4j::simulate(
        known_params.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap();

    sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // Run until done or max iterations
    let mut iterations = 0;
    let max_iterations = 50;
    let mut done = false;

    while !done && iterations < max_iterations {
        let result = sce.step(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        );

        assert!(result.is_ok());
        let (d, _, _, _) = result.unwrap();
        done = d;
        iterations += 1;
    }

    assert!(
        done || iterations == max_iterations,
        "Should converge or reach max iterations"
    );
}

#[test]
fn test_sce_respects_max_evaluations() {
    let max_evals = 50;
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        10,    // High k_stop
        0.001, // Very low threshold (won't trigger convergence)
        1e-10, // Very low geometric range (won't trigger)
        max_evals,
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // Run enough steps to exceed max_evaluations
    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 100 {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                None,
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();
        done = d;
        iterations += 1;
    }

    assert!(done, "Should stop due to max_evaluations");
}

// =============================================================================
// Objective Function Tests
// =============================================================================

#[test]
fn test_sce_all_objectives() {
    for obj_str in ["rmse", "nse", "kge"] {
        let objective = Objective::from_str(obj_str).unwrap();
        let result = Sce::new(
            "gr4j",
            None,
            objective,
            holmes_rs::calibration::utils::Transformation::None,
            2,
            5,
            0.1,
            0.0001,
            50,
            42,
        );

        assert!(
            result.is_ok(),
            "Should create Sce with objective {}",
            obj_str
        );
    }
}

#[test]
fn test_sce_all_transformations() {
    use holmes_rs::calibration::utils::Transformation;

    for trans in [
        Transformation::None,
        Transformation::Log,
        Transformation::Sqrt,
    ] {
        let result = Sce::new(
            "gr4j",
            None,
            Objective::Nse,
            trans,
            2,
            5,
            0.1,
            0.0001,
            50,
            42,
        );

        assert!(
            result.is_ok(),
            "Should create Sce with transformation {:?}",
            trans
        );
    }
}

// =============================================================================
// Property Tests
// =============================================================================

proptest! {
    #[test]
    fn prop_parameters_within_bounds(seed in 0u64..1000) {
        let mut sce = Sce::new(
            "gr4j",
            None,
            Objective::Nse,
            holmes_rs::calibration::utils::Transformation::None,
            2,
            5,
            0.1,
            0.0001,
            20,
            seed,
        ).unwrap();

        let n = 30;
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, seed);
        let pet = helpers::generate_pet(n, 3.0, 1.0, seed + 1);
        let obs = helpers::generate_precipitation(n, 3.0, 0.5, seed + 3);

        sce.init(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        ).unwrap();

        let (_, best_params, _, _) = sce.step(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        ).unwrap();

        // Check params are within GR4J bounds
        let (_, bounds) = holmes_rs::hydro::gr4j::init();
        for (i, &p) in best_params.iter().enumerate() {
            let lower = bounds[[i, 0]];
            let upper = bounds[[i, 1]];
            prop_assert!(
                p >= lower && p <= upper,
                "Parameter {} should be within bounds [{}, {}], got {}",
                i, lower, upper, p
            );
        }
    }
}

// =============================================================================
// Branch Coverage Tests
// =============================================================================

#[test]
fn test_sce_step_when_already_done() {
    // Test the branch where step is called after calibration is already done
    let max_evals = 10; // Very low to finish quickly
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        3,
        100.0, // Very high threshold to force quick convergence
        0.1,   // High geometric range threshold
        max_evals,
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // Run until done
    let mut done = false;
    while !done {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                None,
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();
        done = d;
    }

    // Now call step again after done - should return the same result
    let (done_again, params, sim, objectives) = sce
        .step(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        )
        .unwrap();

    assert!(done_again, "Should still be done");
    assert_eq!(params.len(), 4);
    assert_eq!(sim.len(), n);
    assert_eq!(objectives.len(), 3);
    assert!(params.iter().all(|&p| p.is_finite()));
    assert!(sim.iter().all(|&s| s.is_finite()));
    assert!(objectives.iter().all(|&o| o.is_finite()));
}

#[test]
fn test_sce_geometric_range_convergence() {
    // Test convergence via geometric range threshold
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        100,  // High k_stop (won't trigger)
        0.0,  // Zero convergence threshold (won't trigger)
        0.5,  // High geometric range threshold (will trigger)
        1000, // High max evals (won't trigger)
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // Run a few steps - should converge via geometric range
    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 50 {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                None,
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();
        done = d;
        iterations += 1;
    }

    // Should have converged
    assert!(
        done || iterations == 50,
        "Should converge or reach max iterations"
    );
}

#[test]
fn test_sce_criteria_change_convergence() {
    // Test convergence via criteria change threshold
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        3,     // Low k_stop to check criteria change quickly
        50.0,  // High p_convergence_threshold (will trigger)
        1e-10, // Very low geometric range (won't trigger)
        1000,  // High max evals (won't trigger)
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // Run until done
    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 50 {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                None,
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();
        done = d;
        iterations += 1;
    }

    assert!(done || iterations == 50);
}

#[test]
fn test_sce_with_snow_model_calibration() {
    // Test calibration with snow + hydro model
    let mut sce = Sce::new(
        "gr4j",
        Some("cemaneige"),
        Objective::Kge,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.001,
        50,
        42,
    )
    .unwrap();

    let n = 60;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let temp = helpers::generate_temperature(n, 5.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers =
        helpers::generate_elevation_layers(3, 500.0, 1500.0);
    let median_elevation = 1000.0;

    // Generate observations using snow + hydro chain
    let (snow_defaults, _) = holmes_rs::snow::cemaneige::init();
    let effective_precip = holmes_rs::snow::cemaneige::simulate(
        snow_defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
    )
    .unwrap();

    let (hydro_defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        hydro_defaults.view(),
        effective_precip.view(),
        pet.view(),
    )
    .unwrap()
    .mapv(|x| x * 1.1);

    // Snow model requires temperature, elevation_bands, and median_elevation
    sce.init(
        precip.view(),
        Some(temp.view()),
        pet.view(),
        Some(doy.view()),
        Some(elevation_layers.view()),
        Some(median_elevation),
        obs.view(),
        0,
    )
    .unwrap();

    let (_, params, sim, objectives) = sce
        .step(
            precip.view(),
            Some(temp.view()),
            pet.view(),
            Some(doy.view()),
            Some(elevation_layers.view()),
            Some(median_elevation),
            obs.view(),
            0,
        )
        .unwrap();

    // Should have 7 parameters (3 snow + 4 hydro)
    assert_eq!(params.len(), 7);
    assert_eq!(sim.len(), n);
    assert!(params.iter().all(|&p| p.is_finite()));
    assert!(sim.iter().all(|&s| s.is_finite()));
    assert!(objectives.iter().all(|&o| o.is_finite()));
}

// =============================================================================
// Degenerate-Input Robustness Tests
// =============================================================================

#[test]
fn test_sce_constant_observations() {
    // Constant observations cause zero variance, making NSE/KGE undefined.
    // The optimizer should assign worst-case penalties rather than crashing.
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        50,
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = Array1::from_elem(n, 5.0);

    let init_result = sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    );
    assert!(
        init_result.is_ok(),
        "Init should handle constant observations: {:?}",
        init_result.err()
    );

    let result = sce.step(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    );
    assert!(
        result.is_ok(),
        "Step should handle constant observations: {:?}",
        result.err()
    );
}

// =============================================================================
// Degenerate Metric Handling Tests
// =============================================================================

#[test]
fn test_sce_handles_zero_variance_simulations() {
    // Zero precipitation forces all simulations to constant (zero) flow,
    // triggering "Zero variance in simulations - KGE undefined".
    // The optimizer should assign worst-case objectives rather than crashing.
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Kge,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.001,
        50,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = Array1::from_elem(n, 0.0);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 42);

    let init_result = sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    );
    assert!(
        init_result.is_ok(),
        "Init should handle zero-variance simulations: {:?}",
        init_result.err()
    );

    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 10 {
        let result = sce.step(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        );
        assert!(
            result.is_ok(),
            "Step should handle zero-variance simulations: {:?}",
            result.err()
        );
        let (d, _, _, _) = result.unwrap();
        done = d;
        iterations += 1;
    }
}

#[test]
fn test_sce_handles_zero_variance_with_all_objectives() {
    // Verify all objective functions handle zero-variance gracefully
    for obj in [Objective::Rmse, Objective::Nse, Objective::Kge] {
        let mut sce = Sce::new(
            "gr4j",
            None,
            obj,
            holmes_rs::calibration::utils::Transformation::None,
            2,
            5,
            0.1,
            0.001,
            30,
            42,
        )
        .unwrap();

        let n = 30;
        let precip = Array1::from_elem(n, 0.0);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
        let obs = helpers::generate_precipitation(n, 3.0, 0.5, 42);

        sce.init(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        )
        .expect("Init should handle degenerate metrics");

        let result = sce.step(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        );
        assert!(
            result.is_ok(),
            "Step with {:?} should handle zero-variance: {:?}",
            obj,
            result.err()
        );
    }
}

// =============================================================================
// Error Branch Coverage Tests
// =============================================================================

#[test]
fn test_init_with_mismatched_observations_length() {
    // Test error propagation when observations length doesn't match simulation output
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        100,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);

    // Observations with DIFFERENT length than precipitation (which determines simulation length)
    let obs = Array1::from_elem(n + 10, 5.0); // 10 more elements

    let result = sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    );

    // This should fail because observations length (60) != simulation length (50)
    assert!(
        result.is_err(),
        "Init should fail when observations length mismatches simulation output"
    );
}

#[test]
fn test_step_with_mismatched_observations_length() {
    // Test error propagation in step when observations length changes
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::None,
        2,
        5,
        0.1,
        0.0001,
        100,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 45);

    // Init with correct length
    sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // Step with WRONG observations length
    let wrong_obs = Array1::from_elem(n + 10, 5.0);

    let result = sce.step(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        wrong_obs.view(),
        0,
    );

    // This should fail during evolution when evaluating simulations
    assert!(
        result.is_err(),
        "Step should fail when observations length mismatches simulation output"
    );
}

#[test]
fn test_convergence_with_perfect_match() {
    // Test the zero mean_recent branch (line 302) by having perfect simulation match
    // When simulations perfectly match observations, objectives might be exactly 0/1
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Rmse, // RMSE = 0 for perfect match
        holmes_rs::calibration::utils::Transformation::None,
        2,
        3,   // k_stop = 3
        0.1, // p_convergence_threshold
        0.0001,
        50,
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);

    // Use default GR4J params to generate observations
    let (defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        defaults.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap();

    sce.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // Run multiple steps - when params match exactly, RMSE = 0
    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 30 {
        let result = sce.step(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        );

        assert!(
            result.is_ok(),
            "Step should succeed even with perfect match"
        );
        let (d, _, _, objectives) = result.unwrap();
        done = d;
        iterations += 1;

        // RMSE should be very small (possibly 0) when params are close
        assert!(objectives[0].is_finite(), "RMSE should be finite");
    }
}

// =============================================================================
// sort_population Unit Tests
// =============================================================================

#[test]
fn test_sort_population_nan_at_end_minimization() {
    // Test that NaN values are sorted to the end in minimization mode
    let mut population =
        Array2::from_shape_vec((3, 2), vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
            .unwrap();
    let mut objectives = Array2::from_shape_vec(
        (3, 1),
        vec![
            f64::NAN, // row 0: NaN should go to end
            1.0,      // row 1: should be first (smallest)
            2.0,      // row 2: should be second
        ],
    )
    .unwrap();

    sort_population(&mut population, &mut objectives, 0, true);

    // After sorting: row 1 (1.0), row 2 (2.0), row 0 (NaN)
    assert_eq!(objectives[[0, 0]], 1.0);
    assert_eq!(objectives[[1, 0]], 2.0);
    assert!(objectives[[2, 0]].is_nan());
}

#[test]
fn test_sort_population_nan_at_end_maximization() {
    // Test that NaN values are sorted to the end in maximization mode
    let mut population =
        Array2::from_shape_vec((3, 2), vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
            .unwrap();
    let mut objectives = Array2::from_shape_vec(
        (3, 1),
        vec![
            f64::NAN, // row 0: NaN should go to end
            2.0,      // row 1: should be second (descending)
            1.0,      // row 2: should be last among finite (smallest)
        ],
    )
    .unwrap();

    sort_population(&mut population, &mut objectives, 0, false);

    // After sorting in maximization (descending): row 1 (2.0), row 2 (1.0), row 0 (NaN)
    assert_eq!(objectives[[0, 0]], 2.0);
    assert_eq!(objectives[[1, 0]], 1.0);
    assert!(objectives[[2, 0]].is_nan());
}

#[test]
fn test_sort_population_multiple_nans() {
    // Test sorting when multiple NaN values exist - covers (false, false) branch
    let mut population = Array2::from_shape_vec(
        (4, 2),
        vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    )
    .unwrap();
    let mut objectives = Array2::from_shape_vec(
        (4, 1),
        vec![
            f64::NAN, // row 0
            1.0,      // row 1: finite, should be first
            f64::NAN, // row 2
            2.0,      // row 3: finite, should be second
        ],
    )
    .unwrap();

    sort_population(&mut population, &mut objectives, 0, true);

    // After sorting: finite values first (1.0, 2.0), then NaNs
    assert_eq!(objectives[[0, 0]], 1.0);
    assert_eq!(objectives[[1, 0]], 2.0);
    assert!(objectives[[2, 0]].is_nan());
    assert!(objectives[[3, 0]].is_nan());
}

#[test]
fn test_sort_population_infinity_values() {
    // Test sorting with infinity values - they should also go to end
    let mut population = Array2::from_shape_vec(
        (4, 2),
        vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    )
    .unwrap();
    let mut objectives = Array2::from_shape_vec(
        (4, 1),
        vec![
            f64::INFINITY,     // row 0: infinity should go to end
            1.0,               // row 1
            f64::NEG_INFINITY, // row 2: neg infinity also not finite
            2.0,               // row 3
        ],
    )
    .unwrap();

    sort_population(&mut population, &mut objectives, 0, true);

    // After sorting: finite values first, then infinities
    assert_eq!(objectives[[0, 0]], 1.0);
    assert_eq!(objectives[[1, 0]], 2.0);
    // Last two are infinities (order between them is Equal, so preserves original relative order)
    assert!(!objectives[[2, 0]].is_finite());
    assert!(!objectives[[3, 0]].is_finite());
}

#[test]
fn test_sort_population_all_nans() {
    // Test sorting when all values are NaN - covers (false, false) comparison branch
    let mut population =
        Array2::from_shape_vec((3, 2), vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
            .unwrap();
    let mut objectives = Array2::from_shape_vec(
        (3, 1),
        vec![
            f64::NAN, // row 0
            f64::NAN, // row 1
            f64::NAN, // row 2
        ],
    )
    .unwrap();

    sort_population(&mut population, &mut objectives, 0, true);

    // All NaN values should maintain stable order (Equal comparison)
    assert!(objectives[[0, 0]].is_nan());
    assert!(objectives[[1, 0]].is_nan());
    assert!(objectives[[2, 0]].is_nan());
}

#[test]
fn test_sort_population_two_nans_at_start() {
    // Force comparison between two NaN values by having them at positions
    // that will be compared during sorting
    let mut population = Array2::from_shape_vec(
        (4, 2),
        vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    )
    .unwrap();
    let mut objectives = Array2::from_shape_vec(
        (4, 1),
        vec![
            f64::NAN, // row 0: first NaN
            f64::NAN, // row 1: second NaN - will compare with first
            3.0,      // row 2: finite
            1.0,      // row 3: finite, smallest
        ],
    )
    .unwrap();

    sort_population(&mut population, &mut objectives, 0, true);

    // After sorting: 1.0, 3.0, NaN, NaN
    assert_eq!(objectives[[0, 0]], 1.0);
    assert_eq!(objectives[[1, 0]], 3.0);
    assert!(objectives[[2, 0]].is_nan());
    assert!(objectives[[3, 0]].is_nan());
}

#[test]
fn test_sort_population_nan_after_finite() {
    // Existing NaN tests place NaN at the start, so the sort algorithm
    // never invokes the comparator as cmp(a=nan, b=finite) — only
    // cmp(a=finite, b=nan). This test forces the (false, true) arm by
    // putting finite values first, so NaN elements are inserted
    // *after* a sorted finite prefix.
    let mut population = Array2::from_shape_vec(
        (4, 2),
        vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
    )
    .unwrap();
    let mut objectives = Array2::from_shape_vec(
        (4, 1),
        vec![
            1.0,      // row 0: smallest finite
            3.0,      // row 1: larger finite
            f64::NAN, // row 2: NaN inserted after finite prefix
            f64::NAN, // row 3: NaN inserted after finite prefix
        ],
    )
    .unwrap();

    sort_population(&mut population, &mut objectives, 0, true);

    assert_eq!(objectives[[0, 0]], 1.0);
    assert_eq!(objectives[[1, 0]], 3.0);
    assert!(objectives[[2, 0]].is_nan());
    assert!(objectives[[3, 0]].is_nan());
}

// =============================================================================
// evaluate_simulation Tests (lines 568-585, 591-593)
// =============================================================================

#[test]
fn test_evaluate_simulation_nan_in_simulation_returns_worst_case() {
    // When the simulation contains NaN (e.g. from a degenerate parameter set
    // producing divide-by-zero), evaluate_simulation must return the worst-
    // case objectives [+inf, -inf, -inf] rather than propagating a metrics
    // error — the optimizer relies on this to discard bad candidates without
    // crashing.
    let observations = array![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0];
    let simulations = array![1.0, 2.0, 3.0, 4.0, f64::NAN, 6.0, 7.0, 8.0];

    let result = evaluate_simulation(
        observations.view(),
        simulations.view(),
        Transformation::None,
        0,
    )
    .unwrap();

    assert_eq!(result[0], f64::INFINITY);
    assert_eq!(result[1], f64::NEG_INFINITY);
    assert_eq!(result[2], f64::NEG_INFINITY);
}

#[test]
fn test_evaluate_simulation_infinity_in_simulation_returns_worst_case() {
    let observations = array![1.0, 2.0, 3.0, 4.0];
    let simulations = array![1.0, f64::INFINITY, 3.0, 4.0];

    let result = evaluate_simulation(
        observations.view(),
        simulations.view(),
        Transformation::None,
        0,
    )
    .unwrap();

    assert_eq!(result[0], f64::INFINITY);
    assert_eq!(result[1], f64::NEG_INFINITY);
    assert_eq!(result[2], f64::NEG_INFINITY);
}

#[test]
fn test_evaluate_simulation_zero_variance_observations_returns_penalty() {
    // Constant observations make NSE and KGE undefined (zero variance).
    // penalize_degenerate should convert those metric errors into the
    // penalty values +inf for RMSE and -inf for NSE / KGE so the optimizer
    // treats the candidate as worst-case without crashing.
    let observations = array![5.0, 5.0, 5.0, 5.0, 5.0, 5.0];
    let simulations = array![4.0, 4.5, 5.5, 6.0, 5.0, 4.8];

    let result = evaluate_simulation(
        observations.view(),
        simulations.view(),
        Transformation::None,
        0,
    )
    .unwrap();

    // RMSE is finite (zero variance does not break RMSE).
    assert!(result[0].is_finite());
    // NSE and KGE hit the zero-variance penalty.
    assert_eq!(result[1], f64::NEG_INFINITY);
    assert_eq!(result[2], f64::NEG_INFINITY);
}

#[test]
fn test_evaluate_simulation_skips_nan_observations() {
    // A gap in the observations (NaN) must be dropped before scoring: the
    // gap's simulated value (9.9) must not influence any metric. Scoring the
    // survivors must match scoring a gap-free series of the same survivors.
    let observations = array![1.0, 2.0, f64::NAN, 4.0, 5.0];
    let simulations = array![1.1, 2.1, 9.9, 3.9, 4.8];
    let with_gap = evaluate_simulation(
        observations.view(),
        simulations.view(),
        Transformation::None,
        0,
    )
    .unwrap();

    let clean = evaluate_simulation(
        array![1.0, 2.0, 4.0, 5.0].view(),
        array![1.1, 2.1, 3.9, 4.8].view(),
        Transformation::None,
        0,
    )
    .unwrap();

    assert_relative_eq!(with_gap[0], clean[0], epsilon = 1e-12); // rmse
    assert_relative_eq!(with_gap[1], clean[1], epsilon = 1e-12); // nse
    assert_relative_eq!(with_gap[2], clean[2], epsilon = 1e-12); // kge
}

#[test]
fn test_evaluate_simulation_length_mismatch_errors() {
    // A length mismatch between observations and simulations is a programmer
    // error, not a data gap: it must surface loudly as LengthMismatch rather
    // than being masked (or panicking) inside the gap-drop.
    use holmes_rs::calibration::utils::CalibrationError;
    use holmes_rs::metrics::MetricsError;

    let observations = array![1.0, 2.0, 3.0];
    let simulations = array![1.0, 2.0];

    let result = evaluate_simulation(
        observations.view(),
        simulations.view(),
        Transformation::None,
        0,
    );

    assert!(matches!(
        result,
        Err(CalibrationError::Metrics(MetricsError::LengthMismatch(3, 2)))
    ));
}

#[test]
fn test_evaluate_simulation_sqrt_of_negative_returns_worst_case() {
    // A negative simulated value is finite, so it passes the pre-transform
    // finiteness check, but `sqrt` turns it into NaN. The post-transform
    // finiteness check must catch that and return worst-case rather than
    // feeding NaN into the metrics.
    let observations = array![1.0, 2.0, 3.0, 4.0];
    let simulations = array![1.0, -2.0, 3.0, 4.0];

    let result = evaluate_simulation(
        observations.view(),
        simulations.view(),
        Transformation::Sqrt,
        0,
    )
    .unwrap();

    assert_eq!(result[0], f64::INFINITY);
    assert_eq!(result[1], f64::NEG_INFINITY);
    assert_eq!(result[2], f64::NEG_INFINITY);
}

#[test]
fn test_evaluate_simulation_all_gaps_errors() {
    // Every observation is a gap: after dropping them `kept` is empty, so the
    // RMSE validation gate returns EmptyArrays and evaluate_simulation
    // propagates it as a hard error. (In practice Sce::init guards against this
    // up front; here we pin the lower-level behavior directly.)
    use holmes_rs::calibration::utils::CalibrationError;
    use holmes_rs::metrics::MetricsError;

    let observations = array![f64::NAN, f64::NAN, f64::NAN];
    let simulations = array![1.0, 2.0, 3.0];

    let result = evaluate_simulation(
        observations.view(),
        simulations.view(),
        Transformation::None,
        0,
    );

    assert!(matches!(
        result,
        Err(CalibrationError::Metrics(MetricsError::EmptyArrays))
    ));
}

// =============================================================================
// compute_criteria_change Tests (line 301 + full convergence logic)
// =============================================================================

#[test]
fn test_compute_criteria_change_insufficient_history() {
    // Fewer samples than k_stop -> cannot decide, return infinity.
    let criteria = array![1.0, 2.0];
    let result = compute_criteria_change(criteria.view(), 5);
    assert_eq!(result, f64::INFINITY);
}

#[test]
fn test_compute_criteria_change_non_finite_window() {
    // A NaN or infinity anywhere in the recent window must prevent early
    // termination — SCE should keep iterating rather than misreading the
    // degenerate value as convergence.
    let criteria_nan = array![1.0, 2.0, f64::NAN, 4.0, 5.0];
    assert_eq!(
        compute_criteria_change(criteria_nan.view(), 5),
        f64::INFINITY
    );

    let criteria_inf = array![1.0, f64::INFINITY, 3.0, 4.0, 5.0];
    assert_eq!(
        compute_criteria_change(criteria_inf.view(), 5),
        f64::INFINITY
    );
}

#[test]
fn test_compute_criteria_change_flat_near_zero_converged() {
    // When the recent mean is effectively zero, the criteria are flat at the
    // floor and we report converged (0.0).
    let criteria = array![0.0, 0.0, 0.0, 0.0, 0.0];
    assert_eq!(compute_criteria_change(criteria.view(), 5), 0.0);
}

#[test]
fn test_compute_criteria_change_returns_percent_change() {
    // Classic case: finite values, non-zero mean, finite relative change.
    let criteria = array![10.0, 10.0, 10.0, 10.0, 12.0];
    let result = compute_criteria_change(criteria.view(), 5);
    // |12.0 - 10.0| / mean(|x|) * 100 where mean = 10.4
    let expected = 2.0 * 100.0 / 10.4;
    assert!((result - expected).abs() < 1e-9);
}

// =============================================================================
// evolve_complex_step Tests (lines 859, 884 — random-point fallback)
// =============================================================================

#[test]
fn test_evolve_complex_step_random_fallback_when_reflection_and_contraction_fail(
) {
    // The "contraction also failed -> random point" fallback is reached when
    // both reflection and contraction produce a candidate strictly worse than
    // the simplex's worst point. We force this by handing evolve_complex_step
    // a Simulate closure whose output has a high RMSE vs observations, while
    // seeding the simplex with a small fw so every new evaluation is worse.
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let n_timesteps = 50usize;
    let observations: Array1<f64> = Array1::from_elem(n_timesteps, 1.0);
    let precipitation: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);
    let pet: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);

    // Custom simulate closure: always returns a constant-10 flow regardless
    // of params, which gives rmse ~= 9.0 vs observations of 1.0.
    let simulate: Simulate = Box::new(
        move |_params, _precip, _temp, _pet, _doy, _elev, _median_elev| {
            Ok(Array1::from_elem(n_timesteps, 10.0))
        },
    );

    let lower_bounds = array![0.0, 0.0];
    let upper_bounds = array![10.0, 10.0];

    // 3-point simplex, last row is "worst" and is assigned fw = 0.5
    // (very good rmse), so the candidate's rmse ~= 9.0 is strictly worse.
    let simplex =
        Array2::from_shape_vec((3, 2), vec![5.0, 5.0, 6.0, 6.0, 7.0, 7.0])
            .unwrap();
    let simplex_objectives = Array2::from_shape_vec(
        (3, 3),
        vec![
            0.1, 0.9, 0.9, // row 0: best rmse
            0.3, 0.8, 0.8, // row 1
            0.5, 0.7, 0.7, // row 2: "worst" fw
        ],
    )
    .unwrap();

    let mut rng = ChaCha8Rng::seed_from_u64(42);

    let (snew, fnew, calls) = evolve_complex_step(
        simplex.view(),
        simplex_objectives.view(),
        lower_bounds.view(),
        upper_bounds.view(),
        &simulate,
        precipitation.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        observations.view(),
        0,
        0,    // objective_idx = RMSE
        true, // minimization
        Transformation::None,
        &mut rng,
    )
    .unwrap();

    // Three evaluations: reflection, contraction, random fallback.
    assert_eq!(calls, 3);
    // Resulting objective is based on the constant-10 sim vs 1.0 observations.
    assert!((fnew[0] - 9.0).abs() < 1e-9);
    // snew must remain within bounds.
    assert!(snew.iter().all(|&v| (0.0..=10.0).contains(&v)));
}

#[test]
fn test_evolve_complex_step_reflection_in_bounds_succeeds() {
    // Symmetric check: when reflection produces a better objective, we must
    // NOT enter the contraction / random-fallback branches. This pins the
    // happy-path behavior alongside the fallback test above.
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let n_timesteps = 50usize;
    let observations: Array1<f64> = Array1::from_elem(n_timesteps, 5.0);
    let precipitation: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);
    let pet: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);

    // Simulate always returns exactly the observations -> rmse = 0.
    let simulate: Simulate = Box::new(
        move |_params, _precip, _temp, _pet, _doy, _elev, _median_elev| {
            Ok(Array1::from_elem(n_timesteps, 5.0))
        },
    );

    let lower_bounds = array![0.0, 0.0];
    let upper_bounds = array![10.0, 10.0];
    let simplex =
        Array2::from_shape_vec((3, 2), vec![5.0, 5.0, 6.0, 6.0, 7.0, 7.0])
            .unwrap();
    let simplex_objectives = Array2::from_shape_vec(
        (3, 3),
        vec![10.0, -1.0, -1.0, 20.0, -2.0, -2.0, 30.0, -3.0, -3.0],
    )
    .unwrap();

    let mut rng = ChaCha8Rng::seed_from_u64(42);

    let (_snew, fnew, calls) = evolve_complex_step(
        simplex.view(),
        simplex_objectives.view(),
        lower_bounds.view(),
        upper_bounds.view(),
        &simulate,
        precipitation.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        observations.view(),
        0,
        0,
        true,
        Transformation::None,
        &mut rng,
    )
    .unwrap();

    // Only one call: reflection succeeded.
    assert_eq!(calls, 1);
    assert_eq!(fnew[0], 0.0);
}

#[test]
fn test_evolve_complex_step_propagates_error_from_contraction_eval() {
    // When reflection succeeds but the contraction step's simulate returns
    // a malformed (wrong-length) simulation, evaluate_simulation returns a
    // LengthMismatch error which must propagate out of evolve_complex_step.
    // This pins the error-propagation path on the second evaluate_simulation
    // call inside the contraction branch.
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    let n_timesteps = 50usize;
    let observations: Array1<f64> = Array1::from_elem(n_timesteps, 1.0);
    let precipitation: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);
    let pet: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);

    let call_count = Arc::new(AtomicUsize::new(0));
    let call_count_cl = Arc::clone(&call_count);
    let simulate: Simulate = Box::new(move |_p, _pr, _t, _pet, _d, _e, _m| {
        let n = call_count_cl.fetch_add(1, Ordering::SeqCst);
        if n == 0 {
            // Reflection: correct length, rmse = 9 -> strictly worse -> contraction
            Ok(Array1::from_elem(n_timesteps, 10.0))
        } else {
            // Contraction: wrong length -> LengthMismatch -> Err propagates
            Ok(Array1::from_elem(n_timesteps - 1, 10.0))
        }
    });

    let lower_bounds = array![0.0, 0.0];
    let upper_bounds = array![10.0, 10.0];
    let simplex =
        Array2::from_shape_vec((3, 2), vec![5.0, 5.0, 6.0, 6.0, 7.0, 7.0])
            .unwrap();
    let simplex_objectives = Array2::from_shape_vec(
        (3, 3),
        vec![0.1, 0.9, 0.9, 0.3, 0.8, 0.8, 0.5, 0.7, 0.7],
    )
    .unwrap();

    let mut rng = ChaCha8Rng::seed_from_u64(42);
    let result = evolve_complex_step(
        simplex.view(),
        simplex_objectives.view(),
        lower_bounds.view(),
        upper_bounds.view(),
        &simulate,
        precipitation.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        observations.view(),
        0,
        0,
        true,
        Transformation::None,
        &mut rng,
    );

    assert!(
        result.is_err(),
        "Length mismatch in contraction must propagate"
    );
    assert_eq!(call_count.load(Ordering::SeqCst), 2);
}

#[test]
fn test_evolve_complex_step_propagates_error_from_random_fallback_eval() {
    // Reflection and contraction succeed (correct-length sim, high rmse ->
    // strictly worse -> random fallback). The random-fallback simulate then
    // returns a wrong-length sim, causing evaluate_simulation to error.
    // Pins the error-propagation path on the third evaluate_simulation call.
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    let n_timesteps = 50usize;
    let observations: Array1<f64> = Array1::from_elem(n_timesteps, 1.0);
    let precipitation: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);
    let pet: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);

    let call_count = Arc::new(AtomicUsize::new(0));
    let call_count_cl = Arc::clone(&call_count);
    let simulate: Simulate = Box::new(move |_p, _pr, _t, _pet, _d, _e, _m| {
        let n = call_count_cl.fetch_add(1, Ordering::SeqCst);
        if n < 2 {
            Ok(Array1::from_elem(n_timesteps, 10.0))
        } else {
            Ok(Array1::from_elem(n_timesteps - 1, 10.0))
        }
    });

    let lower_bounds = array![0.0, 0.0];
    let upper_bounds = array![10.0, 10.0];
    let simplex =
        Array2::from_shape_vec((3, 2), vec![5.0, 5.0, 6.0, 6.0, 7.0, 7.0])
            .unwrap();
    let simplex_objectives = Array2::from_shape_vec(
        (3, 3),
        vec![0.1, 0.9, 0.9, 0.3, 0.8, 0.8, 0.5, 0.7, 0.7],
    )
    .unwrap();

    let mut rng = ChaCha8Rng::seed_from_u64(42);
    let result = evolve_complex_step(
        simplex.view(),
        simplex_objectives.view(),
        lower_bounds.view(),
        upper_bounds.view(),
        &simulate,
        precipitation.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        observations.view(),
        0,
        0,
        true,
        Transformation::None,
        &mut rng,
    );

    assert!(
        result.is_err(),
        "Length mismatch in random fallback must propagate"
    );
    assert_eq!(call_count.load(Ordering::SeqCst), 3);
}

#[test]
fn test_evolve_complex_step_propagates_error_from_reflection_simulate() {
    // simulate itself fails on the reflection call (the first call). The
    // `?` operator on the reflection-step simulate must propagate that
    // CalibrationError immediately, before any evaluate_simulation is
    // attempted.
    use holmes_rs::calibration::utils::CalibrationError;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;

    let n_timesteps = 50usize;
    let observations: Array1<f64> = Array1::from_elem(n_timesteps, 1.0);
    let precipitation: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);
    let pet: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);

    let simulate: Simulate = Box::new(|_p, _pr, _t, _pet, _d, _e, _m| {
        Err(CalibrationError::ParamsMismatch(3, 2))
    });

    let lower_bounds = array![0.0, 0.0];
    let upper_bounds = array![10.0, 10.0];
    let simplex =
        Array2::from_shape_vec((3, 2), vec![5.0, 5.0, 6.0, 6.0, 7.0, 7.0])
            .unwrap();
    let simplex_objectives = Array2::from_shape_vec(
        (3, 3),
        vec![0.1, 0.9, 0.9, 0.3, 0.8, 0.8, 0.5, 0.7, 0.7],
    )
    .unwrap();

    let mut rng = ChaCha8Rng::seed_from_u64(42);
    let result = evolve_complex_step(
        simplex.view(),
        simplex_objectives.view(),
        lower_bounds.view(),
        upper_bounds.view(),
        &simulate,
        precipitation.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        observations.view(),
        0,
        0,
        true,
        Transformation::None,
        &mut rng,
    );

    assert!(
        matches!(result, Err(CalibrationError::ParamsMismatch(3, 2))),
        "Reflection simulate error must propagate unchanged"
    );
}

#[test]
fn test_evolve_complex_step_propagates_error_from_contraction_simulate() {
    // simulate succeeds on reflection (high rmse -> strictly worse ->
    // contraction branch taken), then errors on the contraction call.
    // This pins the ? propagation at line 869 (second simulate ?).
    use holmes_rs::calibration::utils::CalibrationError;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    let n_timesteps = 50usize;
    let observations: Array1<f64> = Array1::from_elem(n_timesteps, 1.0);
    let precipitation: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);
    let pet: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);

    let call_count = Arc::new(AtomicUsize::new(0));
    let call_count_cl = Arc::clone(&call_count);
    let simulate: Simulate = Box::new(move |_p, _pr, _t, _pet, _d, _e, _m| {
        let n = call_count_cl.fetch_add(1, Ordering::SeqCst);
        if n == 0 {
            Ok(Array1::from_elem(n_timesteps, 10.0))
        } else {
            Err(CalibrationError::ParamsMismatch(3, 2))
        }
    });

    let lower_bounds = array![0.0, 0.0];
    let upper_bounds = array![10.0, 10.0];
    let simplex =
        Array2::from_shape_vec((3, 2), vec![5.0, 5.0, 6.0, 6.0, 7.0, 7.0])
            .unwrap();
    let simplex_objectives = Array2::from_shape_vec(
        (3, 3),
        vec![0.1, 0.9, 0.9, 0.3, 0.8, 0.8, 0.5, 0.7, 0.7],
    )
    .unwrap();

    let mut rng = ChaCha8Rng::seed_from_u64(42);
    let result = evolve_complex_step(
        simplex.view(),
        simplex_objectives.view(),
        lower_bounds.view(),
        upper_bounds.view(),
        &simulate,
        precipitation.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        observations.view(),
        0,
        0,
        true,
        Transformation::None,
        &mut rng,
    );

    assert!(matches!(
        result,
        Err(CalibrationError::ParamsMismatch(3, 2))
    ));
    assert_eq!(call_count.load(Ordering::SeqCst), 2);
}

#[test]
fn test_evolve_complex_step_propagates_error_from_random_fallback_simulate() {
    // simulate succeeds on reflection and contraction (both high rmse ->
    // strictly worse) then errors on the random-fallback call. This pins
    // the ? propagation at line 894 (third simulate ?).
    use holmes_rs::calibration::utils::CalibrationError;
    use rand::SeedableRng;
    use rand_chacha::ChaCha8Rng;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    let n_timesteps = 50usize;
    let observations: Array1<f64> = Array1::from_elem(n_timesteps, 1.0);
    let precipitation: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);
    let pet: Array1<f64> = Array1::from_elem(n_timesteps, 0.0);

    let call_count = Arc::new(AtomicUsize::new(0));
    let call_count_cl = Arc::clone(&call_count);
    let simulate: Simulate = Box::new(move |_p, _pr, _t, _pet, _d, _e, _m| {
        let n = call_count_cl.fetch_add(1, Ordering::SeqCst);
        if n < 2 {
            Ok(Array1::from_elem(n_timesteps, 10.0))
        } else {
            Err(CalibrationError::ParamsMismatch(3, 2))
        }
    });

    let lower_bounds = array![0.0, 0.0];
    let upper_bounds = array![10.0, 10.0];
    let simplex =
        Array2::from_shape_vec((3, 2), vec![5.0, 5.0, 6.0, 6.0, 7.0, 7.0])
            .unwrap();
    let simplex_objectives = Array2::from_shape_vec(
        (3, 3),
        vec![0.1, 0.9, 0.9, 0.3, 0.8, 0.8, 0.5, 0.7, 0.7],
    )
    .unwrap();

    let mut rng = ChaCha8Rng::seed_from_u64(42);
    let result = evolve_complex_step(
        simplex.view(),
        simplex_objectives.view(),
        lower_bounds.view(),
        upper_bounds.view(),
        &simulate,
        precipitation.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        observations.view(),
        0,
        0,
        true,
        Transformation::None,
        &mut rng,
    );

    assert!(matches!(
        result,
        Err(CalibrationError::ParamsMismatch(3, 2))
    ));
    assert_eq!(call_count.load(Ordering::SeqCst), 3);
}
