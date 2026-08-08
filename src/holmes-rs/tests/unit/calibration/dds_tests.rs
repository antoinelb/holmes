use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::calibration::dds::{
    perturb_candidate, reflect_at_bounds, Dds,
};
use holmes_rs::calibration::utils::{
    CalibrationError, Objective, Transformation,
};
use ndarray::{array, Array1};
use proptest::prelude::*;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

// =============================================================================
// Constructor Tests
// =============================================================================

#[test]
fn test_dds_new_gr4j_only() {
    let result = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2, // r
        100, // max_evaluations
        42,  // seed
    );

    assert!(result.is_ok(), "Should create Dds with GR4J only");
}

#[test]
fn test_dds_new_gr4j_cemaneige() {
    let result = Dds::new(
        "gr4j",
        Some("cemaneige"),
        Objective::Kge,
        Transformation::Log,
        0.2,
        100,
        42,
    );

    assert!(result.is_ok(), "Should create Dds with GR4J + CemaNeige");
}

#[test]
fn test_dds_new_invalid_hydro_model() {
    let result = Dds::new(
        "invalid_model",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        100,
        42,
    );

    assert!(result.is_err(), "Should fail with invalid hydro model");
}

#[test]
fn test_dds_new_invalid_snow_model() {
    let result = Dds::new(
        "gr4j",
        Some("invalid_snow"),
        Objective::Nse,
        Transformation::None,
        0.2,
        100,
        42,
    );

    assert!(result.is_err(), "Should fail with invalid snow model");
}

#[test]
fn test_dds_new_invalid_r() {
    // r must be finite and in (0, 1]: the perturbation standard deviation is
    // r * (upper - lower), so r = 0 never moves and r > 1 or non-finite r is
    // a caller bug.
    for r in [0.0, -0.5, 1.5, f64::NAN, f64::INFINITY] {
        let result = Dds::new(
            "gr4j",
            None,
            Objective::Nse,
            Transformation::None,
            r,
            100,
            42,
        );
        assert!(
            matches!(result, Err(CalibrationError::InvalidParameter(_))),
            "r = {} should be rejected",
            r
        );
    }
}

#[test]
fn test_dds_new_r_boundary_accepted() {
    // r = 1.0 is the inclusive upper limit of the valid range.
    let result = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        1.0,
        100,
        42,
    );
    assert!(result.is_ok(), "r = 1.0 should be accepted");
}

#[test]
fn test_dds_new_invalid_max_evaluations() {
    // The perturbation probability is 1 - ln(i)/ln(m): m = 1 divides by zero,
    // and m = 0 makes no sense as a budget.
    for max_evaluations in [0, 1] {
        let result = Dds::new(
            "gr4j",
            None,
            Objective::Nse,
            Transformation::None,
            0.2,
            max_evaluations,
            42,
        );
        assert!(
            matches!(result, Err(CalibrationError::InvalidParameter(_))),
            "max_evaluations = {} should be rejected",
            max_evaluations
        );
    }
}

// =============================================================================
// Initialization Tests
// =============================================================================

#[test]
fn test_dds_init_basic() {
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        1000,
        42,
    )
    .unwrap();

    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);

    let (defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        defaults.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap()
    .mapv(|x| x * 1.1);

    let result = dds.init(
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
fn test_dds_init_all_missing_observations_errors() {
    // Every timestep after warmup is a gap (NaN). Init must fail loudly with
    // NoObservations rather than aborting later with a generic EmptyArrays
    // message from evaluate_simulation.
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        100,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = Array1::from_elem(n, f64::NAN);

    let result = dds.init(
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

#[test]
fn test_dds_init_with_mismatched_observations_length() {
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        100,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = Array1::from_elem(n + 10, 5.0);

    let result = dds.init(
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
        result.is_err(),
        "Init should fail when observations length mismatches simulation output"
    );
}

// =============================================================================
// Step Tests
// =============================================================================

#[test]
fn test_dds_step_returns_valid_output() {
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        50,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);

    let (defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        defaults.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap()
    .mapv(|x| x * 1.1);

    dds.init(
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

    let result = dds.step(
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

    assert_eq!(best_params.len(), 4, "Should have 4 GR4J parameters");
    assert_eq!(best_sim.len(), n, "Simulation should match input length");
    assert_eq!(
        objectives.len(),
        3,
        "Should have 3 objectives (RMSE, NSE, KGE)"
    );

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
fn test_dds_respects_exact_evaluation_budget() {
    // DDS stops on the evaluation budget alone: init consumes 1 evaluation,
    // each step exactly 1 more, so done must flip on step max_evaluations - 1.
    let max_evals = 10;
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        max_evals,
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    dds.init(
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

    let mut iterations = 0;
    let mut done = false;
    while !done && iterations < 100 {
        let (d, _, _, _) = dds
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
    assert_eq!(
        iterations,
        max_evals - 1,
        "init consumes 1 evaluation and each step exactly 1 more"
    );
}

#[test]
fn test_dds_step_when_already_done() {
    let max_evals = 5;
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        max_evals,
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 99);

    dds.init(
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

    let mut done = false;
    let mut last_params = Array1::zeros(4);
    let mut last_objectives = Array1::zeros(3);
    while !done {
        let (d, params, _, objectives) = dds
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
        last_params = params;
        last_objectives = objectives;
    }

    // Calling step again after done must return the same best without
    // consuming further evaluations.
    let (done_again, params, sim, objectives) = dds
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
    assert_eq!(sim.len(), n);
    for i in 0..4 {
        assert_relative_eq!(params[i], last_params[i], epsilon = 1e-12);
    }
    for i in 0..3 {
        assert_relative_eq!(
            objectives[i],
            last_objectives[i],
            epsilon = 1e-12
        );
    }
}

#[test]
fn test_dds_greedy_never_worsens() {
    // The incumbent is only replaced by a candidate at least as good, so the
    // best objective must be monotonic across the whole run (non-decreasing
    // for NSE, which is maximized).
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        100,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let known_params = array![300.0, 0.5, 100.0, 2.5];
    let obs = holmes_rs::hydro::gr4j::simulate(
        known_params.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap();

    dds.init(
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

    let mut previous_nse = f64::NEG_INFINITY;
    let mut done = false;
    while !done {
        let (d, _, _, objectives) = dds
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
        assert!(
            objectives[1] >= previous_nse,
            "Best NSE must never decrease: {} < {}",
            objectives[1],
            previous_nse
        );
        previous_nse = objectives[1];
    }
}

#[test]
fn test_dds_rmse_minimization_never_worsens() {
    // Same greedy invariant through the minimization branch: RMSE must be
    // monotonically non-increasing.
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Rmse,
        Transformation::None,
        0.2,
        50,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let (defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        defaults.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap()
    .mapv(|x| x * 1.1);

    dds.init(
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

    let mut previous_rmse = f64::INFINITY;
    let mut done = false;
    while !done {
        let (d, _, _, objectives) = dds
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
        assert!(
            objectives[0] <= previous_rmse,
            "Best RMSE must never increase: {} > {}",
            objectives[0],
            previous_rmse
        );
        previous_rmse = objectives[0];
    }
}

#[test]
fn test_dds_reproducibility() {
    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);
    let (defaults, _) = holmes_rs::hydro::gr4j::init();
    let obs = holmes_rs::hydro::gr4j::simulate(
        defaults.view(),
        precip.view(),
        pet.view(),
    )
    .unwrap()
    .mapv(|x| x * 1.1);

    let mut results = Vec::new();

    for _ in 0..2 {
        let mut dds = Dds::new(
            "gr4j",
            None,
            Objective::Nse,
            Transformation::None,
            0.2,
            20,
            42, // Same seed
        )
        .unwrap();

        dds.init(
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

        let mut done = false;
        let mut last = (Array1::zeros(4), Array1::zeros(3));
        while !done {
            let (d, params, _, objectives) = dds
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
            last = (params, objectives);
        }
        results.push(last);
    }

    for i in 0..4 {
        assert_relative_eq!(results[0].0[i], results[1].0[i], epsilon = 1e-12);
    }
    for i in 0..3 {
        assert_relative_eq!(results[0].1[i], results[1].1[i], epsilon = 1e-12);
    }
}

#[test]
fn test_dds_step_with_mismatched_observations_length() {
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        100,
        42,
    )
    .unwrap();

    let n = 50;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = helpers::generate_precipitation(n, 3.0, 0.5, 45);

    dds.init(
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

    let wrong_obs = Array1::from_elem(n + 10, 5.0);

    let result = dds.step(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        wrong_obs.view(),
        0,
    );

    assert!(
        result.is_err(),
        "Step should fail when observations length mismatches simulation output"
    );
}

#[test]
fn test_dds_with_snow_model_calibration() {
    let mut dds = Dds::new(
        "gr4j",
        Some("cemaneige"),
        Objective::Kge,
        Transformation::None,
        0.2,
        30,
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

    dds.init(
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

    let (_, params, sim, objectives) = dds
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
fn test_dds_constant_observations() {
    // Constant observations cause zero variance, making NSE/KGE undefined.
    // The optimizer should assign worst-case penalties rather than crashing.
    let mut dds = Dds::new(
        "gr4j",
        None,
        Objective::Nse,
        Transformation::None,
        0.2,
        10,
        42,
    )
    .unwrap();

    let n = 30;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
    let obs = Array1::from_elem(n, 5.0);

    dds.init(
        precip.view(),
        None,
        pet.view(),
        None,
        None,
        None,
        obs.view(),
        0,
    )
    .expect("Init should handle constant observations");

    let mut done = false;
    while !done {
        let result = dds.step(
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
        let (d, _, _, _) = result.unwrap();
        done = d;
    }
}

#[test]
fn test_dds_handles_zero_variance_with_all_objectives() {
    // Zero precipitation forces all simulations to constant (zero) flow,
    // making the metrics degenerate for every candidate. The greedy
    // acceptance must tolerate comparing worst-case values (inf vs inf)
    // without crashing, for all three objectives.
    for obj in [Objective::Rmse, Objective::Nse, Objective::Kge] {
        let mut dds = Dds::new(
            "gr4j",
            None,
            obj,
            Transformation::None,
            0.2,
            10,
            42,
        )
        .unwrap();

        let n = 30;
        let precip = Array1::from_elem(n, 0.0);
        let pet = helpers::generate_pet(n, 3.0, 1.0, 44);
        let obs = helpers::generate_precipitation(n, 3.0, 0.5, 42);

        dds.init(
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

        let mut done = false;
        while !done {
            let result = dds.step(
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
            let (d, _, _, _) = result.unwrap();
            done = d;
        }
    }
}

// =============================================================================
// Objective / Transformation Coverage
// =============================================================================

#[test]
fn test_dds_all_transformations() {
    for trans in [
        Transformation::None,
        Transformation::Log,
        Transformation::Sqrt,
    ] {
        let result = Dds::new(
            "gr4j",
            None,
            Objective::Nse,
            trans,
            0.2,
            50,
            42,
        );

        assert!(
            result.is_ok(),
            "Should create Dds with transformation {:?}",
            trans
        );
    }
}

// =============================================================================
// perturb_candidate / reflect_at_bounds Unit Tests
// =============================================================================

#[test]
fn test_reflect_at_bounds_within_bounds_unchanged() {
    assert_eq!(reflect_at_bounds(5.0, 0.0, 10.0), 5.0);
    assert_eq!(reflect_at_bounds(0.0, 0.0, 10.0), 0.0);
    assert_eq!(reflect_at_bounds(10.0, 0.0, 10.0), 10.0);
}

#[test]
fn test_reflect_at_bounds_below_lower_reflects() {
    // -2 undershoots the lower bound 0 by 2 -> bounces back to 2.
    assert_relative_eq!(reflect_at_bounds(-2.0, 0.0, 10.0), 2.0);
}

#[test]
fn test_reflect_at_bounds_above_upper_reflects() {
    // 13 overshoots the upper bound 10 by 3 -> bounces back to 7.
    assert_relative_eq!(reflect_at_bounds(13.0, 0.0, 10.0), 7.0);
}

#[test]
fn test_reflect_at_bounds_reflection_overshoot_clamps_to_violated_bound() {
    // -15 undershoots lower=0 by 15; the bounce to 15 crosses upper=10, so
    // the value is set to the violated (lower) bound, per the paper.
    assert_eq!(reflect_at_bounds(-15.0, 0.0, 10.0), 0.0);
    // 25 overshoots upper=10 by 15; the bounce to -5 crosses lower=0, so the
    // value is set to the violated (upper) bound.
    assert_eq!(reflect_at_bounds(25.0, 0.0, 10.0), 10.0);
}

#[test]
fn test_perturb_candidate_zero_probability_moves_exactly_one_dimension() {
    // With inclusion probability 0, no dimension is selected stochastically,
    // so the mandatory fallback must perturb exactly one random dimension.
    let best = array![5.0, 5.0, 5.0, 5.0];
    let lower = array![0.0, 0.0, 0.0, 0.0];
    let upper = array![10.0, 10.0, 10.0, 10.0];
    let mut rng = ChaCha8Rng::seed_from_u64(42);

    let candidate = perturb_candidate(
        best.view(),
        lower.view(),
        upper.view(),
        0.2,
        0.0,
        &mut rng,
    );

    let n_changed = candidate
        .iter()
        .zip(best.iter())
        .filter(|(c, b)| c != b)
        .count();
    assert_eq!(n_changed, 1, "Exactly one dimension must be perturbed");
}

#[test]
fn test_perturb_candidate_full_probability_moves_all_dimensions() {
    // With inclusion probability 1, every dimension is selected (a standard
    // normal draw is never exactly zero in practice).
    let best = array![5.0, 5.0, 5.0, 5.0];
    let lower = array![0.0, 0.0, 0.0, 0.0];
    let upper = array![10.0, 10.0, 10.0, 10.0];
    let mut rng = ChaCha8Rng::seed_from_u64(42);

    let candidate = perturb_candidate(
        best.view(),
        lower.view(),
        upper.view(),
        0.2,
        1.0,
        &mut rng,
    );

    let n_changed = candidate
        .iter()
        .zip(best.iter())
        .filter(|(c, b)| c != b)
        .count();
    assert_eq!(n_changed, 4, "All dimensions must be perturbed");
}

proptest! {
    #[test]
    fn prop_perturb_candidate_stays_within_bounds(
        seed in 0u64..1000,
        probability in 0.0f64..=1.0,
    ) {
        // Large r maximizes the chance of bound violations, exercising the
        // reflection logic; the candidate must always land inside the bounds.
        let best = array![0.5, 999.0, 0.01, 5.0];
        let lower = array![0.0, 0.0, 0.0, 0.0];
        let upper = array![1.0, 1000.0, 0.02, 10.0];
        let mut rng = ChaCha8Rng::seed_from_u64(seed);

        let candidate = perturb_candidate(
            best.view(),
            lower.view(),
            upper.view(),
            1.0,
            probability,
            &mut rng,
        );

        for i in 0..4 {
            prop_assert!(
                candidate[i] >= lower[i] && candidate[i] <= upper[i],
                "Dimension {} out of bounds: {}",
                i,
                candidate[i]
            );
        }
    }

    #[test]
    fn prop_dds_parameters_within_bounds(seed in 0u64..100) {
        let mut dds = Dds::new(
            "gr4j",
            None,
            Objective::Nse,
            Transformation::None,
            0.2,
            10,
            seed,
        ).unwrap();

        let n = 30;
        let precip = helpers::generate_precipitation(n, 5.0, 0.3, seed);
        let pet = helpers::generate_pet(n, 3.0, 1.0, seed + 1);
        let obs = helpers::generate_precipitation(n, 3.0, 0.5, seed + 3);

        dds.init(
            precip.view(),
            None,
            pet.view(),
            None,
            None,
            None,
            obs.view(),
            0,
        ).unwrap();

        let mut done = false;
        while !done {
            let (d, best_params, _, _) = dds.step(
                precip.view(),
                None,
                pet.view(),
                None,
                None,
                None,
                obs.view(),
                0,
            ).unwrap();
            done = d;

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
}
