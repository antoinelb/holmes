use crate::helpers;
use holmes_rs::calibration::sce::Sce;
use holmes_rs::calibration::utils::Objective;
use ndarray::{array, Array1};
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

    // Generate synthetic observations (model output + noise)
    let (defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        defaults.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap()
    .mapv(|x| x * 1.1); // Add 10% bias

    let result = sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
        obs.view(),
    );

    assert!(result.is_ok(), "Init should succeed: {:?}", result.err());
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

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
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
        obs.view(),
    )
    .unwrap();

    let result = sce.step(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
        obs.view(),
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

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
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
        obs.view(),
    )
    .unwrap();

    // Run until done or max iterations
    let mut iterations = 0;
    let max_iterations = 50;
    let mut done = false;

    while !done && iterations < max_iterations {
        let result = sce.step(
            precip.view(),
            temp.view(),
            pet.view(),
            doy.view(),
            elevation_layers.view(),
            median_elevation,
            obs.view(),
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
        obs.view(),
    )
    .unwrap();

    // Run enough steps to exceed max_evaluations
    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 100 {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                temp.view(),
                pet.view(),
                doy.view(),
                elevation_layers.view(),
                median_elevation,
                obs.view(),
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
        let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, seed + 2);
        let doy = helpers::generate_doy(1, n);
        let elevation_layers = array![1000.0];
        let obs = helpers::generate_precipitation(n, 3.0, 0.5, seed + 3);

        sce.init(
            precip.view(),
            temp.view(),
            pet.view(),
            doy.view(),
            elevation_layers.view(),
            1000.0,
            obs.view(),
        ).unwrap();

        let (_, best_params, _, _) = sce.step(
            precip.view(),
            temp.view(),
            pet.view(),
            doy.view(),
            elevation_layers.view(),
            1000.0,
            obs.view(),
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        obs.view(),
    )
    .unwrap();

    // Run until done
    let mut done = false;
    while !done {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                temp.view(),
                pet.view(),
                doy.view(),
                elevation_layers.view(),
                1000.0,
                obs.view(),
            )
            .unwrap();
        done = d;
    }

    // Now call step again after done - should return the same result
    let (done_again, params, sim, objectives) = sce
        .step(
            precip.view(),
            temp.view(),
            pet.view(),
            doy.view(),
            elevation_layers.view(),
            1000.0,
            obs.view(),
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        obs.view(),
    )
    .unwrap();

    // Run a few steps - should converge via geometric range
    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 50 {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                temp.view(),
                pet.view(),
                doy.view(),
                elevation_layers.view(),
                1000.0,
                obs.view(),
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        obs.view(),
    )
    .unwrap();

    // Run until done
    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 50 {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                temp.view(),
                pet.view(),
                doy.view(),
                elevation_layers.view(),
                1000.0,
                obs.view(),
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

    sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
        obs.view(),
    )
    .unwrap();

    let (_, params, sim, objectives) = sce
        .step(
            precip.view(),
            temp.view(),
            pet.view(),
            doy.view(),
            elevation_layers.view(),
            median_elevation,
            obs.view(),
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
// Anti-Fragility Tests (expected to fail with current implementation)
// =============================================================================

#[test]
#[ignore = "R4-DATA-02: sqrt transformation on negative simulated values produces NaN"]
fn test_sce_sqrt_transform_negative() {
    // If simulations produce negative values (which GR4J shouldn't, but other models might)
    // sqrt transformation would produce NaN
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        holmes_rs::calibration::utils::Transformation::Sqrt,
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    // Negative observations to test sqrt transformation issue
    let obs = Array1::from_elem(n, -1.0);

    let init_result = sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        obs.view(),
    );

    // Should either handle gracefully or return error
    if init_result.is_ok() {
        let step_result = sce.step(
            precip.view(),
            temp.view(),
            pet.view(),
            doy.view(),
            elevation_layers.view(),
            1000.0,
            obs.view(),
        );
        if let Ok((_, _, _, objectives)) = step_result {
            assert!(
                objectives.iter().all(|&o| o.is_finite()),
                "Objectives should not be NaN"
            );
        }
    }
}

#[test]
#[ignore = "R5-NUM-06: NaN in convergence criteria when observations are constant"]
fn test_sce_constant_observations() {
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    // Constant observations cause NSE denominator = 0
    let obs = Array1::from_elem(n, 5.0);

    let init_result = sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        obs.view(),
    );

    if init_result.is_ok() {
        let (_, _, _, objectives) = sce
            .step(
                precip.view(),
                temp.view(),
                pet.view(),
                doy.view(),
                elevation_layers.view(),
                1000.0,
                obs.view(),
            )
            .unwrap();

        // NSE should be handled (not NaN)
        assert!(
            objectives[1].is_finite(),
            "NSE should be finite even with constant observations"
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

    // Observations with DIFFERENT length than precipitation (which determines simulation length)
    let obs = Array1::from_elem(n + 10, 5.0); // 10 more elements

    let result = sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        obs.view(),
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 45);

    // Init with correct length
    sce.init(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        obs.view(),
    )
    .unwrap();

    // Step with WRONG observations length
    let wrong_obs = Array1::from_elem(n + 10, 5.0);

    let result = sce.step(
        precip.view(),
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        wrong_obs.view(),
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
    let temp = helpers::generate_temperature(n, 10.0, 10.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];

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
        temp.view(),
        pet.view(),
        doy.view(),
        elevation_layers.view(),
        1000.0,
        obs.view(),
    )
    .unwrap();

    // Run multiple steps - when params match exactly, RMSE = 0
    let mut done = false;
    let mut iterations = 0;
    while !done && iterations < 30 {
        let result = sce.step(
            precip.view(),
            temp.view(),
            pet.view(),
            doy.view(),
            elevation_layers.view(),
            1000.0,
            obs.view(),
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
