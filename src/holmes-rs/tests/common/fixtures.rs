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

/// One row of a raw catchment observations fixture (`Date,P,E0,Qo,T`), as
/// copied verbatim from `src/holmes/data/<name>_Observations.csv`.
#[derive(Debug, Deserialize)]
pub struct RawObservationRecord {
    #[serde(rename = "Date")]
    pub date: String,
    #[serde(rename = "P")]
    pub precipitation: f64,
    #[serde(rename = "E0")]
    pub pet: f64,
    #[serde(rename = "Qo")]
    pub observed_flow: Option<f64>,
    #[serde(rename = "T")]
    pub temperature: f64,
}

/// Catchment forcing and observations ready for the calibration API.
pub struct CatchmentData {
    pub precipitation: Array1<f64>,
    pub temperature: Array1<f64>,
    pub pet: Array1<f64>,
    /// NaN where the streamflow observation is missing.
    pub observed_flow: Array1<f64>,
    pub day_of_year: Array1<usize>,
}

/// Load a raw catchment observations fixture (`Date,P,E0,Qo,T`). Missing
/// streamflow values become NaN. `day_of_year` follows the convention of
/// `scripts/run_experiments.py`: `((ordinal_day - 1) % 365) + 1`, which maps
/// day 366 of leap years onto day 1.
pub fn load_catchment_data(
    path: &Path,
) -> Result<CatchmentData, Box<dyn std::error::Error>> {
    let mut reader = csv::Reader::from_path(path)?;
    let records: Vec<RawObservationRecord> =
        reader.deserialize().collect::<Result<_, _>>()?;
    if records.is_empty() {
        return Err(format!("empty observations fixture: {:?}", path).into());
    }

    let mut precipitation = Vec::with_capacity(records.len());
    let mut temperature = Vec::with_capacity(records.len());
    let mut pet = Vec::with_capacity(records.len());
    let mut observed_flow = Vec::with_capacity(records.len());
    let mut doy = Vec::with_capacity(records.len());
    for record in &records {
        precipitation.push(record.precipitation);
        temperature.push(record.temperature);
        pet.push(record.pet);
        observed_flow.push(record.observed_flow.unwrap_or(f64::NAN));
        doy.push((day_of_year(&record.date)? - 1) % 365 + 1);
    }

    Ok(CatchmentData {
        precipitation: Array1::from_vec(precipitation),
        temperature: Array1::from_vec(temperature),
        pet: Array1::from_vec(pet),
        observed_flow: Array1::from_vec(observed_flow),
        day_of_year: Array1::from_vec(doy),
    })
}

/// Day of year (1-366) from a `YYYY-MM-DD` date string.
fn day_of_year(date: &str) -> Result<usize, Box<dyn std::error::Error>> {
    const CUMULATIVE_DAYS: [usize; 12] =
        [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];

    let mut parts = date.split('-');
    let mut next_number =
        |name: &str| -> Result<i64, Box<dyn std::error::Error>> {
            Ok(parts
                .next()
                .ok_or_else(|| {
                    format!("date '{}' is missing its {}", date, name)
                })?
                .parse::<i64>()?)
        };
    let year = next_number("year")?;
    let month = next_number("month")?;
    let day = next_number("day")?;
    if !(1..=12).contains(&month) || !(1..=31).contains(&day) {
        return Err(format!("invalid date: {}", date).into());
    }

    let leap = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    let leap_offset = if leap && month > 2 { 1 } else { 0 };
    Ok(CUMULATIVE_DAYS[month as usize - 1] + day as usize + leap_offset)
}

/// CemaNeige catchment metadata from a `<name>_CemaNeigeInfo.csv` fixture
/// (`key,value` lines; `AltiBand` is `;`-separated).
pub struct CemaNeigeInfo {
    pub qnbv: f64,
    pub elevation_bands: Array1<f64>,
    pub median_elevation: f64,
    pub latitude: f64,
}

/// Load a CemaNeige info fixture. Unknown keys are ignored; missing required
/// keys are an error.
pub fn load_cemaneige_info(
    path: &Path,
) -> Result<CemaNeigeInfo, Box<dyn std::error::Error>> {
    let contents = std::fs::read_to_string(path)?;

    let mut qnbv = None;
    let mut elevation_bands = None;
    let mut median_elevation = None;
    let mut latitude = None;
    for line in contents.lines().filter(|l| !l.trim().is_empty()) {
        let (key, value) = line.split_once(',').ok_or_else(|| {
            format!("malformed CemaNeigeInfo line: {}", line)
        })?;
        match key {
            "QNBV" => qnbv = Some(value.parse::<f64>()?),
            "AltiBand" => {
                elevation_bands = Some(Array1::from_vec(
                    value
                        .split(';')
                        .map(|v| v.parse::<f64>())
                        .collect::<Result<Vec<f64>, _>>()?,
                ))
            }
            "Z50" => median_elevation = Some(value.parse::<f64>()?),
            "Lat" => latitude = Some(value.parse::<f64>()?),
            _ => {}
        }
    }

    let missing = |key: &str| format!("missing {} in {:?}", key, path);
    Ok(CemaNeigeInfo {
        qnbv: qnbv.ok_or_else(|| missing("QNBV"))?,
        elevation_bands: elevation_bands.ok_or_else(|| missing("AltiBand"))?,
        median_elevation: median_elevation.ok_or_else(|| missing("Z50"))?,
        latitude: latitude.ok_or_else(|| missing("Lat"))?,
    })
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

    #[test]
    fn test_load_catchment_data_au_saumon() {
        let data = load_catchment_data(
            &fixtures_dir().join("observations_au_saumon.csv"),
        )
        .unwrap();

        let n = data.precipitation.len();
        assert!(n > 10_000, "Au Saumon record should span ~29 years");
        assert_eq!(data.temperature.len(), n);
        assert_eq!(data.pet.len(), n);
        assert_eq!(data.observed_flow.len(), n);
        assert_eq!(data.day_of_year.len(), n);

        // First row: 1975-03-01,7.67,...,0.63,-3.75 -> ordinal day 60
        assert_eq!(data.precipitation[0], 7.67);
        assert_eq!(data.observed_flow[0], 0.63);
        assert_eq!(data.temperature[0], -3.75);
        assert_eq!(data.day_of_year[0], 60);

        assert!(data.day_of_year.iter().all(|&d| (1..=365).contains(&d)));
    }

    #[test]
    fn test_day_of_year_convention() {
        // Non-leap year boundaries.
        assert_eq!(day_of_year("1975-01-01").unwrap(), 1);
        assert_eq!(day_of_year("1975-12-31").unwrap(), 365);
        // Leap year: Mar 1 is ordinal day 61; Dec 31 is 366, which the
        // loader's `((d - 1) % 365) + 1` maps to 1 (script convention).
        assert_eq!(day_of_year("1976-03-01").unwrap(), 61);
        assert_eq!(day_of_year("1976-12-31").unwrap(), 366);

        assert!(day_of_year("1976-13-01").is_err());
        assert!(day_of_year("1976-01").is_err());
        assert!(day_of_year("not-a-date").is_err());
    }

    #[test]
    fn test_load_cemaneige_info_au_saumon() {
        let info = load_cemaneige_info(
            &fixtures_dir().join("cemaneige_info_au_saumon.csv"),
        )
        .unwrap();

        assert_eq!(info.qnbv, 354.9);
        assert_eq!(info.elevation_bands.len(), 5);
        assert_eq!(info.elevation_bands[0], 379.0);
        assert_eq!(info.median_elevation, 474.0);
        assert_eq!(info.latitude, 45.482);
    }
}
