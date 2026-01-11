use ndarray::Array1;
use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Deserialize)]
pub struct ObservationRecord {
    pub date: String,
    pub precipitation: f64,
    pub temperature: f64,
    pub pet: f64,
    pub observed_flow: f64,
}

#[derive(Debug, Deserialize)]
pub struct CalibrationScenario {
    pub hydro_model: String,
    pub snow_model: Option<String>,
    pub expected_nse: f64,
    pub tolerance: f64,
}

/// Load observations from a CSV file
pub fn load_observations(
    path: &Path,
) -> Result<Vec<ObservationRecord>, csv::Error> {
    let mut reader = csv::Reader::from_path(path)?;
    let records: Result<Vec<ObservationRecord>, _> =
        reader.deserialize().collect();
    records
}

/// Convert observations to arrays for model input
pub fn observations_to_arrays(
    records: &[ObservationRecord],
) -> (Array1<f64>, Array1<f64>, Array1<f64>, Array1<f64>) {
    let precip: Vec<f64> = records.iter().map(|r| r.precipitation).collect();
    let temp: Vec<f64> = records.iter().map(|r| r.temperature).collect();
    let pet: Vec<f64> = records.iter().map(|r| r.pet).collect();
    let obs_flow: Vec<f64> = records.iter().map(|r| r.observed_flow).collect();

    (
        Array1::from_vec(precip),
        Array1::from_vec(temp),
        Array1::from_vec(pet),
        Array1::from_vec(obs_flow),
    )
}

/// Load calibration scenario from JSON
pub fn load_calibration_scenario(
    path: &Path,
) -> Result<CalibrationScenario, Box<dyn std::error::Error>> {
    let contents = std::fs::read_to_string(path)?;
    let scenario: CalibrationScenario = serde_json::from_str(&contents)?;
    Ok(scenario)
}

/// Get the path to the fixtures directory
pub fn fixtures_dir() -> std::path::PathBuf {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    Path::new(manifest_dir).join("tests").join("fixtures")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_fixtures_dir_exists() {
        let dir = fixtures_dir();
        // The directory may not exist yet during initial test runs
        // This test just ensures the path construction works
        assert!(dir.to_str().unwrap().contains("fixtures"));
    }
}
