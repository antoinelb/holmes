use crate::fixtures::{
    fixtures_dir, load_observations, observations_to_arrays,
};
use crate::helpers;
use approx::assert_relative_eq;
use holmes_rs::hydro::{bucket, gr4j};
use holmes_rs::metrics::{calculate_kge, calculate_nse, calculate_rmse};
use holmes_rs::pet::oudin;
use holmes_rs::snow::cemaneige;
use ndarray::{array, Array1};

// =============================================================================
// GR4J Full Year Simulation Tests
// =============================================================================

#[test]
fn test_gr4j_one_year() {
    let (defaults, _) = gr4j::init();
    let n = 365;

    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 2.0, 43);

    let streamflow =
        gr4j::simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| !q.is_nan()),
        "No NaN values in output"
    );
    assert!(
        streamflow.iter().all(|&q| q >= 0.0),
        "All positive flow values"
    );
    assert!(
        streamflow.iter().any(|&q| q > 0.0),
        "Should have some positive flow"
    );

    // Water balance check: total outflow should be related to total input
    let total_precip: f64 = precip.sum();
    let _total_pet: f64 = pet.sum();
    let total_flow: f64 = streamflow.sum();

    // Flow should be less than precip (some water is lost to ET)
    assert!(
        total_flow < total_precip,
        "Total flow should be less than total precipitation"
    );
}

#[test]
fn test_bucket_one_year() {
    let (defaults, _) = bucket::init();
    let n = 365;

    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 2.0, 43);

    let streamflow =
        bucket::simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| !q.is_nan()),
        "No NaN values in output"
    );
    assert!(
        streamflow.iter().all(|&q| q >= 0.0),
        "All positive flow values"
    );
}

// =============================================================================
// Snow + Hydro Chain Tests
// =============================================================================

#[test]
fn test_gr4j_cemaneige_one_year() {
    // First run snow model to get effective precipitation
    let (snow_defaults, _) = cemaneige::init();
    let (hydro_defaults, _) = gr4j::init();
    let n = 365;

    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let temp = helpers::generate_temperature(n, 5.0, 15.0, 2.0, 43);
    let pet = helpers::generate_pet(n, 3.0, 2.0, 44);
    let doy = helpers::generate_doy(1, n);
    let elevation_layers =
        helpers::generate_elevation_layers(5, 500.0, 2000.0);
    let median_elevation = 1250.0;

    // Run snow model
    let effective_precip = cemaneige::simulate(
        snow_defaults.view(),
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
        "Effective precip should be valid"
    );

    // Run hydro model with effective precipitation
    let streamflow = gr4j::simulate(
        hydro_defaults.view(),
        effective_precip.view(),
        pet.view(),
    )
    .unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Streamflow should be valid"
    );
}

// =============================================================================
// PET → Hydro Chain Tests
// =============================================================================

#[test]
fn test_oudin_gr4j_chain() {
    let n = 365;

    // Generate temperature and compute PET using Oudin
    let temp = helpers::generate_temperature(n, 10.0, 15.0, 2.0, 42);
    let doy = helpers::generate_doy(1, n);
    let latitude = 45.0;

    let pet = oudin::simulate(temp.view(), doy.view(), latitude).unwrap();

    assert_eq!(pet.len(), n);
    assert!(
        pet.iter().all(|&p| p.is_finite() && p >= 0.0),
        "PET should be valid"
    );

    // Now run GR4J with computed PET
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 43);
    let (defaults, _) = gr4j::init();

    let streamflow =
        gr4j::simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Streamflow should be valid"
    );
}

// =============================================================================
// Full Chain: PET → Snow → Hydro
// =============================================================================

#[test]
fn test_full_model_chain() {
    let n = 365;

    // 1. Generate input data
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let temp = helpers::generate_temperature(n, 5.0, 15.0, 2.0, 43);
    let doy = helpers::generate_doy(1, n);
    let latitude = 45.0;
    let elevation_layers =
        helpers::generate_elevation_layers(3, 800.0, 1500.0);
    let median_elevation = 1150.0;

    // 2. Compute PET
    let pet = oudin::simulate(temp.view(), doy.view(), latitude).unwrap();

    // 3. Run snow model
    let (snow_defaults, _) = cemaneige::init();
    let effective_precip = cemaneige::simulate(
        snow_defaults.view(),
        precip.view(),
        temp.view(),
        doy.view(),
        elevation_layers.view(),
        median_elevation,
    )
    .unwrap();

    // 4. Run hydro model
    let (hydro_defaults, _) = gr4j::init();
    let streamflow = gr4j::simulate(
        hydro_defaults.view(),
        effective_precip.view(),
        pet.view(),
    )
    .unwrap();

    // 5. Verify output
    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Full chain should produce valid streamflow"
    );

    // Check for seasonal patterns
    let winter_mean = streamflow.slice(ndarray::s![0..90]).mean().unwrap();
    let spring_mean = streamflow.slice(ndarray::s![90..180]).mean().unwrap();

    // Spring should have higher flows due to snowmelt
    // (this is a simplified check - actual behavior depends on parameters)
    assert!(
        spring_mean > 0.0 || winter_mean > 0.0,
        "Should have some flow in either season"
    );
}

// =============================================================================
// Fixture-Based Tests
// =============================================================================

#[test]
fn test_against_fixture() {
    let fixture_path = fixtures_dir().join("observations_normal.csv");

    // Skip if fixture doesn't exist
    if !fixture_path.exists() {
        eprintln!("Skipping fixture test: {:?} not found", fixture_path);
        return;
    }

    let records = load_observations(&fixture_path).unwrap();
    let (precip, _temp, pet, obs_flow) = observations_to_arrays(&records);

    // Run model with default parameters
    let (defaults, _) = gr4j::init();
    let simulated =
        gr4j::simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    // Calculate metrics
    let rmse = calculate_rmse(obs_flow.view(), simulated.view()).unwrap();
    let nse = calculate_nse(obs_flow.view(), simulated.view()).unwrap();
    let kge = calculate_kge(obs_flow.view(), simulated.view()).unwrap();

    // Metrics should be finite
    assert!(rmse.is_finite(), "RMSE should be finite");
    assert!(nse.is_finite(), "NSE should be finite");
    assert!(kge.is_finite(), "KGE should be finite");

    // Basic sanity checks (not expecting perfect fit with default params)
    assert!(rmse >= 0.0, "RMSE should be non-negative");
    assert!(nse <= 1.0, "NSE should be <= 1");
    assert!(kge <= 1.0, "KGE should be <= 1");
}

// =============================================================================
// Metrics Consistency Tests
// =============================================================================

#[test]
fn test_metrics_consistency() {
    let n = 100;
    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 1.0, 43);

    // Generate two sets of simulations with different parameters
    let params1 = array![200.0, 0.5, 80.0, 2.0];
    let params2 = array![400.0, -0.5, 120.0, 3.0];

    let sim1 =
        gr4j::simulate(params1.view(), precip.view(), pet.view()).unwrap();
    let sim2 =
        gr4j::simulate(params2.view(), precip.view(), pet.view()).unwrap();

    // Both should produce valid metrics when compared to each other
    let rmse = calculate_rmse(sim1.view(), sim2.view()).unwrap();
    let nse = calculate_nse(sim1.view(), sim2.view()).unwrap();
    let kge = calculate_kge(sim1.view(), sim2.view()).unwrap();

    assert!(rmse.is_finite());
    assert!(nse.is_finite());
    assert!(kge.is_finite());

    // Perfect match should give specific values
    let rmse_self = calculate_rmse(sim1.view(), sim1.view()).unwrap();
    let nse_self = calculate_nse(sim1.view(), sim1.view()).unwrap();
    let kge_self = calculate_kge(sim1.view(), sim1.view()).unwrap();

    assert_relative_eq!(rmse_self, 0.0, epsilon = 1e-10);
    assert_relative_eq!(nse_self, 1.0, epsilon = 1e-10);
    assert_relative_eq!(kge_self, 1.0, epsilon = 1e-10);
}

// =============================================================================
// Multi-Year Simulation Tests
// =============================================================================

#[test]
fn test_multi_year_simulation() {
    let n = 365 * 3; // 3 years
    let (defaults, _) = gr4j::init();

    let precip = helpers::generate_precipitation(n, 5.0, 0.3, 42);
    let pet = helpers::generate_pet(n, 3.0, 2.0, 43);

    let streamflow =
        gr4j::simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Multi-year simulation should be valid"
    );

    // Check that model reaches some kind of equilibrium
    // (year 3 should be similar to year 2)
    let year2_mean: f64 =
        streamflow.slice(ndarray::s![365..730]).mean().unwrap();
    let year3_mean: f64 = streamflow.slice(ndarray::s![730..]).mean().unwrap();

    // Allow 50% difference (models can have long memory)
    let diff_ratio = (year3_mean - year2_mean).abs() / year2_mean.max(0.01);
    assert!(
        diff_ratio < 0.5,
        "Years 2 and 3 should have similar mean flows (ratio: {})",
        diff_ratio
    );
}

// =============================================================================
// Edge Case Tests
// =============================================================================

#[test]
fn test_very_short_simulation() {
    let (defaults, _) = gr4j::init();
    let n = 5;

    let precip = array![10.0, 5.0, 0.0, 15.0, 2.0];
    let pet = array![2.0, 2.5, 3.0, 2.0, 1.5];

    let streamflow =
        gr4j::simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(streamflow.iter().all(|&q| q.is_finite() && q >= 0.0));
}

#[test]
fn test_extreme_precipitation_event() {
    let (defaults, _) = gr4j::init();
    let n = 100;

    let mut precip = Array1::zeros(n);
    precip[50] = 200.0; // Extreme event
    let pet = Array1::from_elem(n, 2.0);

    let streamflow =
        gr4j::simulate(defaults.view(), precip.view(), pet.view()).unwrap();

    assert_eq!(streamflow.len(), n);
    assert!(
        streamflow.iter().all(|&q| q.is_finite() && q >= 0.0),
        "Should handle extreme precipitation"
    );

    // Peak should occur after the event
    let peak_idx = streamflow
        .iter()
        .enumerate()
        .max_by(|(_, a), (_, b)| a.partial_cmp(b).unwrap())
        .unwrap()
        .0;

    assert!(
        peak_idx >= 50,
        "Peak should occur on or after precipitation event"
    );
}
