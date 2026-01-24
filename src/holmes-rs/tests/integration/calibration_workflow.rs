use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::calibration::sce::Sce;
use holmes_rs::calibration::utils::{Objective, Transformation};
use holmes_rs::hydro::gr4j;
use holmes_rs::metrics::{calculate_kge, calculate_nse, calculate_rmse};
use ndarray::{array, Array1};

// =============================================================================
// Synthetic Parameter Recovery Tests
// =============================================================================

#[test]
fn test_sce_synthetic_convergence() {
    // Generate synthetic observations from known parameters
    let known_params = array![300.0, 0.5, 100.0, 2.5];
    let n = 100;

    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let doy = helpers::generate_doy(1, n);

    // Generate observations from known parameters
    let obs = gr4j::simulate(known_params.view(), precip.view(), pet.view())
        .unwrap();

    // Create calibrator
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        3,     // n_complexes
        5,     // k_stop
        0.5,   // p_convergence_threshold
        0.001, // geometric_range_threshold
        500,   // max_evaluations
        42,    // seed
    )
    .unwrap();

    // Initialize (no snow model, so snow params are None)
    sce.init(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // Run until convergence
    let mut done = false;
    let mut best_params = Array1::zeros(4);
    let mut best_nse = f64::NEG_INFINITY;
    let mut iterations = 0;

    while !done && iterations < 100 {
        let (d, params, _, objectives) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                doy.view(),
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();

        done = d;
        best_params = params;
        best_nse = objectives[1]; // NSE is index 1
        iterations += 1;
    }

    // Should achieve good NSE (observations are exact model output)
    assert!(
        best_nse > 0.95,
        "Should achieve NSE > 0.95 for synthetic data, got {}",
        best_nse
    );

    // Verify simulation with recovered params
    let sim =
        gr4j::simulate(best_params.view(), precip.view(), pet.view()).unwrap();
    let final_nse = calculate_nse(obs.view(), sim.view()).unwrap();
    assert!(
        final_nse > 0.95,
        "Final NSE should be > 0.95, got {}",
        final_nse
    );
}

// =============================================================================
// Objective Function Tests
// =============================================================================

#[test]
fn test_sce_rmse_objective() {
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let doy = helpers::generate_doy(1, n);

    // Generate observations with some noise
    let (defaults, _) = gr4j::init();
    let obs = gr4j::simulate(defaults.view(), precip.view(), pet.view())
        .unwrap()
        .mapv(|x| x * 1.1);

    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Rmse,
        Transformation::None,
        2,
        5,
        0.5,
        0.001,
        100,
        42,
    )
    .unwrap();

    sce.init(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    let mut done = false;
    let mut iterations = 0;
    let mut final_rmse = f64::INFINITY;

    while !done && iterations < 30 {
        let (d, _, _, objectives) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                doy.view(),
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();

        done = d;
        final_rmse = objectives[0]; // RMSE is index 0
        iterations += 1;
    }

    // RMSE should improve
    assert!(
        final_rmse.is_finite() && final_rmse >= 0.0,
        "Final RMSE should be valid"
    );
}

#[test]
fn test_sce_kge_objective() {
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let doy = helpers::generate_doy(1, n);

    let (defaults, _) = gr4j::init();
    let obs = gr4j::simulate(defaults.view(), precip.view(), pet.view())
        .unwrap()
        .mapv(|x| x * 1.1);

    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Kge,
        Transformation::None,
        2,
        5,
        0.5,
        0.001,
        100,
        42,
    )
    .unwrap();

    sce.init(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    let mut done = false;
    let mut iterations = 0;
    let mut final_kge = f64::NEG_INFINITY;

    while !done && iterations < 30 {
        let (d, _, _, objectives) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                doy.view(),
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();

        done = d;
        final_kge = objectives[2]; // KGE is index 2
        iterations += 1;
    }

    assert!(
        final_kge.is_finite() && final_kge <= 1.0,
        "Final KGE should be valid"
    );
}

// =============================================================================
// Transformation Tests
// =============================================================================

#[test]
fn test_sce_log_transformation() {
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let doy = helpers::generate_doy(1, n);

    // Ensure positive observations for log transform
    let (defaults, _) = gr4j::init();
    let obs = gr4j::simulate(defaults.view(), precip.view(), pet.view())
        .unwrap()
        .mapv(|x| (x + 1.0) * 1.1);

    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::Log,
        2,
        5,
        0.5,
        0.001,
        100,
        42,
    )
    .unwrap();

    let init_result = sce.init(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    );

    assert!(init_result.is_ok(), "Log transformation should work");

    let step_result = sce.step(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    );

    assert!(
        step_result.is_ok(),
        "Step with log transformation should work"
    );

    let (_, _, _, objectives) = step_result.unwrap();
    assert!(
        objectives.iter().all(|&o| o.is_finite()),
        "All objectives should be finite with log transform"
    );
}

#[test]
fn test_sce_sqrt_transformation() {
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let doy = helpers::generate_doy(1, n);

    // Positive observations for sqrt transform
    let (defaults, _) = gr4j::init();
    let obs = gr4j::simulate(defaults.view(), precip.view(), pet.view())
        .unwrap()
        .mapv(|x| x + 1.0);

    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::Sqrt,
        2,
        5,
        0.5,
        0.001,
        100,
        42,
    )
    .unwrap();

    let init_result = sce.init(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    );

    assert!(init_result.is_ok(), "Sqrt transformation should work");

    let step_result = sce.step(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    );

    assert!(
        step_result.is_ok(),
        "Step with sqrt transformation should work"
    );
}

// =============================================================================
// Max Evaluations Test
// =============================================================================

#[test]
fn test_sce_max_evaluations() {
    let max_evals = 30;
    let n = 30;

    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let doy = helpers::generate_doy(1, n);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        2,
        10,    // High k_stop to not trigger convergence early
        0.001, // Very low threshold
        1e-10, // Very low geometric range
        max_evals,
        42,
    )
    .unwrap();

    sce.init(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    let mut iterations = 0;
    let mut done = false;

    while !done && iterations < 100 {
        let (d, _, _, _) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                doy.view(),
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();
        done = d;
        iterations += 1;
    }

    assert!(
        done,
        "Should stop due to max_evaluations within {} iterations",
        iterations
    );
}

// =============================================================================
// Combined Snow + Hydro Calibration
// =============================================================================

#[test]
fn test_sce_snow_hydro_calibration() {
    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let temp = helpers::generate_temperature(n, 5.0, 15.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers = array![1000.0];
    let median_elevation = 1000.0;

    // Generate synthetic observations using both snow and hydro models
    let snow_params = array![0.5, 5.0, 350.0];
    let hydro_params = array![300.0, 0.5, 100.0, 2.5];

    let effective_precip = holmes_rs::snow::cemaneige::simulate(
        snow_params.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
    )
    .unwrap();

    let obs = gr4j::simulate(
        hydro_params.view(),
        effective_precip.view(),
        pet.view(),
    )
    .unwrap();

    // Create calibrator with both models
    let mut sce = Sce::new(
        "gr4j",
        Some("cemaneige"),
        Objective::Nse,
        Transformation::None,
        2,
        5,
        0.5,
        0.001,
        200,
        42,
    )
    .unwrap();

    // Snow model requires temperature, elevation_bands, and median_elevation
    sce.init(
        precip.view(),
        Some(temp.view()),
        pet.view(),
        doy.view(),
        Some(elevation_layers.view()),
        Some(median_elevation),
        obs.view(),
        0,
    )
    .unwrap();

    let mut done = false;
    let mut iterations = 0;
    let mut final_nse = f64::NEG_INFINITY;
    let mut best_params = Array1::zeros(7); // 3 snow + 4 hydro

    while !done && iterations < 50 {
        let (d, params, _, objectives) = sce
            .step(
                precip.view(),
                Some(temp.view()),
                pet.view(),
                doy.view(),
                Some(elevation_layers.view()),
                Some(median_elevation),
                obs.view(),
                0,
            )
            .unwrap();

        done = d;
        best_params = params;
        final_nse = objectives[1];
        iterations += 1;
    }

    // Should have 7 parameters (3 snow + 4 hydro)
    assert_eq!(
        best_params.len(),
        7,
        "Should calibrate 7 parameters (snow + hydro)"
    );

    // Should achieve reasonable NSE
    assert!(
        final_nse > 0.5,
        "Should achieve NSE > 0.5 for snow+hydro calibration, got {}",
        final_nse
    );
}

// =============================================================================
// Reproducibility Test
// =============================================================================

#[test]
fn test_sce_reproducibility() {
    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let doy = helpers::generate_doy(1, n);

    let (defaults, _) = gr4j::init();
    let obs = gr4j::simulate(defaults.view(), precip.view(), pet.view())
        .unwrap()
        .mapv(|x| x * 1.1);

    // Run twice with same seed
    let mut results = Vec::new();

    for _ in 0..2 {
        let mut sce = Sce::new(
            "gr4j",
            None,
            Objective::Nse,
            Transformation::None,
            2,
            5,
            0.5,
            0.001,
            50,
            42, // Same seed
        )
        .unwrap();

        sce.init(
            precip.view(),
            None,
            pet.view(),
            doy.view(),
            None,
            None,
            obs.view(),
            0,
        )
        .unwrap();

        let (_, params, _, objectives) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                doy.view(),
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();

        results.push((params.to_vec(), objectives.to_vec()));
    }

    // Results should be identical with same seed
    for i in 0..4 {
        assert_relative_eq!(results[0].0[i], results[1].0[i], epsilon = 1e-10);
    }
    for i in 0..3 {
        assert_relative_eq!(results[0].1[i], results[1].1[i], epsilon = 1e-10);
    }
}

// =============================================================================
// Full End-to-End Calibration
// =============================================================================

#[test]
fn test_full_calibration_workflow() {
    // This test demonstrates a complete calibration workflow

    // 1. Define the problem
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let doy = helpers::generate_doy(1, n);

    // 2. Generate "observed" data (with known parameters for testing)
    let true_params = array![250.0, 0.3, 80.0, 2.0];
    let obs =
        gr4j::simulate(true_params.view(), precip.view(), pet.view()).unwrap();

    // 3. Create and configure calibrator
    let mut sce = Sce::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        3,      // n_complexes
        5,      // k_stop
        0.2,    // p_convergence_threshold
        0.0005, // geometric_range_threshold
        500,    // max_evaluations
        123,    // seed
    )
    .unwrap();

    // 4. Initialize (no snow model, so snow params are None)
    sce.init(
        precip.view(),
        None,
        pet.view(),
        doy.view(),
        None,
        None,
        obs.view(),
        0,
    )
    .unwrap();

    // 5. Run calibration
    let mut done = false;
    let mut iterations = 0;
    let mut best_sim = Array1::zeros(n);
    let mut best_objectives = Array1::zeros(3);

    while !done && iterations < 100 {
        let (d, _params, sim, objectives) = sce
            .step(
                precip.view(),
                None,
                pet.view(),
                doy.view(),
                None,
                None,
                obs.view(),
                0,
            )
            .unwrap();

        done = d;
        best_sim = sim;
        best_objectives = objectives;
        iterations += 1;
    }

    // 6. Verify results
    assert!(
        best_objectives[1] > 0.9,
        "Calibration should achieve NSE > 0.9, got {}",
        best_objectives[1]
    );

    // 7. Validate simulation quality
    let final_rmse = calculate_rmse(obs.view(), best_sim.view()).unwrap();
    let final_nse = calculate_nse(obs.view(), best_sim.view()).unwrap();
    let final_kge = calculate_kge(obs.view(), best_sim.view()).unwrap();

    assert!(final_rmse < 0.5, "Final RMSE should be low");
    assert!(final_nse > 0.9, "Final NSE should be high");
    assert!(final_kge > 0.9, "Final KGE should be high");
}
