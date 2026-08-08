use ndarray::{s, Array1, Array2, ArrayView1, Axis};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rand_chacha::ChaCha8Rng;
use std::str::FromStr;
use thiserror::Error;

use crate::hydro::{HydroError, HydroSimulate};
use crate::metrics::{
    calculate_kge, calculate_nse, calculate_rmse, MetricsError,
};
use crate::snow::{SnowError, SnowSimulate};

pub type Simulate = Box<
    dyn Fn(
            ArrayView1<f64>,           // params
            ArrayView1<f64>,           // precipitation
            Option<ArrayView1<f64>>, // temperature (optional - only needed for snow)
            ArrayView1<f64>,         // pet
            Option<ArrayView1<usize>>, // day_of_year (optional - only needed for snow)
            Option<ArrayView1<f64>>, // elevation_bands (optional - only needed for snow)
            Option<f64>, // median_elevation (optional - only needed for snow)
        ) -> Result<Array1<f64>, CalibrationError>
        + Sync
        + Send,
>;

pub struct CalibrationParams {
    pub params: Array1<f64>,
    pub simulate: Simulate,
    pub lower_bounds: Array1<f64>,
    pub upper_bounds: Array1<f64>,
    pub objective: Objective,
    pub transformation: Transformation,
    pub rng: ChaCha8Rng,
    pub done: bool,
}

#[derive(Debug, Clone, Copy)]
pub enum Objective {
    Rmse,
    Nse,
    Kge,
}

impl FromStr for Objective {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "rmse" => Ok(Self::Rmse),
            "nse" => Ok(Self::Nse),
            "kge" => Ok(Self::Kge),
            _ => Err(format!(
                "Unknown objective function '{}'. Valid options: nse, kge, rmse",
                s
            )),
        }
    }
}

#[derive(Debug, Clone, Copy)]
pub enum Transformation {
    Log,
    Sqrt,
    None,
}

impl FromStr for Transformation {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "log" => Ok(Self::Log),
            "sqrt" => Ok(Self::Sqrt),
            "none" => Ok(Self::None),
            _ => Err(format!(
                "Unknown transformation function '{}'. Valid options: log, sqrt, none",
                s
            )),
        }
    }
}

#[derive(Error, Debug)]
pub enum CalibrationError {
    #[error(
        "precipitation, temperature, pet and day_of_year must have the same length (got {0}, {1}, {2} and {3})"
    )]
    LengthMismatch(usize, usize, usize, usize),
    #[error("expected {0} params, got {1}")]
    ParamsMismatch(usize, usize),
    #[error("snow model requires temperature, day_of_year, elevation_bands, and median_elevation")]
    MissingSnowParams,
    #[error(
        "no streamflow observations available in the calibration window \
         (every timestep after warmup is missing)"
    )]
    NoObservations,
    #[error("invalid algorithm parameter: {0}")]
    InvalidParameter(String),
    #[error(transparent)]
    Metrics(#[from] MetricsError),
    #[error(transparent)]
    Hydro(#[from] HydroError),
    #[error(transparent)]
    Snow(#[from] SnowError),
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<CalibrationError> for PyErr {
    fn from(err: CalibrationError) -> PyErr {
        match err {
            CalibrationError::Metrics(e) => e.into(),
            CalibrationError::Hydro(e) => e.into(),
            CalibrationError::Snow(e) => e.into(),
            _ => PyValueError::new_err(err.to_string()),
        }
    }
}

pub fn check_lengths(
    precipitation: ArrayView1<f64>,
    temperature: Option<ArrayView1<f64>>,
    pet: ArrayView1<f64>,
    day_of_year: Option<ArrayView1<usize>>,
) -> Result<(), CalibrationError> {
    let temp_len = temperature.map(|t| t.len()).unwrap_or(precipitation.len());
    let doy_len = day_of_year.map(|d| d.len()).unwrap_or(precipitation.len());
    if precipitation.len() != pet.len()
        || precipitation.len() != temp_len
        || precipitation.len() != doy_len
    {
        Err(CalibrationError::LengthMismatch(
            precipitation.len(),
            temp_len,
            pet.len(),
            doy_len,
        ))
    } else {
        Ok(())
    }
}

/// Build the simulate closure, default parameters, and bounds for a hydro
/// model with an optional snow model (snow parameters are prepended).
/// Shared by all calibration algorithms.
pub fn build_simulate(
    hydro_model: &str,
    snow_model: Option<&str>,
) -> Result<(Simulate, Array1<f64>, Array2<f64>), CalibrationError> {
    if let Some(snow_model) = snow_model {
        let (snow_init, snow_simulate) = crate::snow::get_model(snow_model)?;
        let (hydro_init, hydro_simulate) =
            crate::hydro::get_model(hydro_model)?;

        let (snow_defaults, snow_bounds) = snow_init();
        let (hydro_defaults, hydro_bounds) = hydro_init();
        let n_snow_params = snow_defaults.len();
        let simulate = compose_simulate(
            Some(snow_simulate),
            hydro_simulate,
            n_snow_params,
        );
        Ok((
            simulate,
            ndarray::concatenate(
                Axis(0),
                &[snow_defaults.view(), hydro_defaults.view()],
            )
            .expect("concatenating 1-D parameter arrays cannot fail"),
            ndarray::concatenate(
                Axis(0),
                &[snow_bounds.view(), hydro_bounds.view()],
            )
            .expect(
                "concatenating bounds with identical column count cannot fail",
            ),
        ))
    } else {
        let (hydro_init, hydro_simulate) =
            crate::hydro::get_model(hydro_model)?;
        let (defaults, bounds) = hydro_init();
        let simulate = compose_simulate(None, hydro_simulate, 0);
        Ok((simulate, defaults, bounds))
    }
}

/// Compute all three objectives (rmse, nse, kge) from a simulation.
/// Shared by all calibration algorithms; exposed for integration tests.
pub fn evaluate_simulation(
    observations: ArrayView1<f64>,
    simulations: ArrayView1<f64>,
    transformation: Transformation,
    warmup_steps: usize,
) -> Result<Array1<f64>, CalibrationError> {
    let observations = observations.slice(s![warmup_steps..]);
    let simulations = simulations.slice(s![warmup_steps..]);

    // A non-finite value anywhere in the simulated trajectory signals a
    // degenerate parameter set. Check the FULL window before dropping gaps so
    // the "NaN simulation -> worst case" invariant can't be masked by a gap
    // that happens to coincide with the NaN.
    if simulations.iter().any(|x| !x.is_finite()) {
        return Ok(worst_case_objectives());
    }

    // A length mismatch is a programmer error, not a data gap. Reject it
    // explicitly and up front: the gap-drop below aligns by observation index,
    // so an unequal `simulations` would panic in `select` (obs longer) or have
    // the mismatch silently masked (obs shorter). This raises the same
    // LengthMismatch the RMSE gate would, just loudly and before any work.
    if observations.len() != simulations.len() {
        return Err(CalibrationError::Metrics(MetricsError::LengthMismatch(
            observations.len(),
            simulations.len(),
        )));
    }

    // Drop timesteps with no streamflow observation (NaN gaps): the metric is
    // scored only where a measurement exists. MUST run before the transform --
    // `f64::NAN.max(1e-5)` returns 1e-5, so a gap would otherwise be silently
    // turned into ln(1e-5) under the log transform.
    let kept: Vec<usize> = observations
        .iter()
        .enumerate()
        .filter(|(_, o)| o.is_finite())
        .map(|(i, _)| i)
        .collect();
    let observations = observations.select(Axis(0), &kept);
    let simulations = simulations.select(Axis(0), &kept);

    let (observations, simulations) = match transformation {
        Transformation::Log => (
            observations.mapv(|x| x.max(1e-5).ln()),
            simulations.mapv(|x| x.max(1e-5).ln()),
        ),
        Transformation::Sqrt => (
            observations.mapv(|x| x.sqrt()),
            simulations.mapv(|x| x.sqrt()),
        ),
        Transformation::None => (observations, simulations),
    };

    // The sqrt transform can introduce NaN from a negative simulated value at a
    // scored timestep; penalize rather than crash.
    if simulations.iter().any(|x| !x.is_finite()) {
        return Ok(worst_case_objectives());
    }

    // RMSE is the validation gate. If `kept` is empty (all-observations
    // missing), RMSE returns EmptyArrays here and `?` propagates it as a hard
    // error -- callers guard against this up front with NoObservations.
    let rmse = penalize_degenerate(
        calculate_rmse(observations.view(), simulations.view()),
        f64::INFINITY,
    )?;
    let nse = penalize_degenerate(
        calculate_nse(observations.view(), simulations.view()),
        f64::NEG_INFINITY,
    )
    .expect("NSE cannot return a non-degenerate error once RMSE has validated inputs");
    let kge = penalize_degenerate(
        calculate_kge(observations.view(), simulations.view()),
        f64::NEG_INFINITY,
    )
    .expect("KGE cannot return a non-degenerate error once RMSE has validated inputs");

    Ok(Array1::from_vec(vec![rmse, nse, kge]))
}

/// Returns worst-case objective values for each metric during optimization.
/// RMSE is minimized (worst = INFINITY), NSE and KGE are maximized
/// (worst = NEG_INFINITY).
pub fn worst_case_objectives() -> Array1<f64> {
    Array1::from_vec(vec![f64::INFINITY, f64::NEG_INFINITY, f64::NEG_INFINITY])
}

/// During optimization, degenerate parameter sets can produce simulations with
/// zero variance or other numerical issues that make metrics undefined.
/// Returns a penalty value instead of propagating the error. Data validation
/// errors (length mismatch, empty arrays) still propagate since they indicate
/// bugs rather than bad parameter sets.
fn penalize_degenerate(
    result: Result<f64, MetricsError>,
    penalty: f64,
) -> Result<f64, CalibrationError> {
    match result {
        Ok(v) => Ok(v),
        Err(
            MetricsError::ZeroVarianceNSE
            | MetricsError::ZeroVarianceKGE { .. }
            | MetricsError::ZeroMeanKGE
            | MetricsError::NumericalError { .. },
        ) => Ok(penalty),
        Err(e) => Err(CalibrationError::Metrics(e)),
    }
}

pub fn compose_simulate(
    snow_simulate: Option<SnowSimulate>,
    hydro_simulate: HydroSimulate,
    n_snow_params: usize,
) -> Simulate {
    Box::new(
        move |params,
              precipitation,
              temperature,
              pet,
              day_of_year,
              elevation_bands,
              median_elevation| {
            check_lengths(precipitation, temperature, pet, day_of_year)?;
            if let Some(snow_simulate) = snow_simulate {
                // Snow model requires temperature, day_of_year, elevation_bands, and median_elevation
                let temperature =
                    temperature.ok_or(CalibrationError::MissingSnowParams)?;
                let day_of_year =
                    day_of_year.ok_or(CalibrationError::MissingSnowParams)?;
                let elevation_bands = elevation_bands
                    .ok_or(CalibrationError::MissingSnowParams)?;
                let median_elevation = median_elevation
                    .ok_or(CalibrationError::MissingSnowParams)?;

                let snow_params = params.slice(s![..n_snow_params]);
                let hydro_params = params.slice(s![n_snow_params..]);

                let effective_precipitation = snow_simulate(
                    snow_params,
                    precipitation,
                    temperature,
                    day_of_year,
                    elevation_bands,
                    median_elevation,
                )
                .map_err(CalibrationError::Snow)?;

                hydro_simulate(
                    hydro_params,
                    effective_precipitation.view(),
                    pet,
                )
                .map_err(CalibrationError::Hydro)
            } else {
                // No snow model - snow params are not needed
                hydro_simulate(params, precipitation, pet)
                    .map_err(CalibrationError::Hydro)
            }
        },
    )
}
