use ndarray::{s, Array1, ArrayView1};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rand_chacha::ChaCha8Rng;
use std::str::FromStr;
use thiserror::Error;

use crate::hydro::{HydroError, HydroSimulate};
use crate::metrics::MetricsError;
use crate::snow::{SnowError, SnowSimulate};

pub type Simulate = Box<
    dyn Fn(
            ArrayView1<f64>,
            ArrayView1<f64>,
            ArrayView1<f64>,
            ArrayView1<f64>,
            ArrayView1<usize>,
            ArrayView1<f64>,
            f64,
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
        PyValueError::new_err(err.to_string())
    }
}

pub fn check_lengths(
    precipitation: ArrayView1<f64>,
    temperature: ArrayView1<f64>,
    pet: ArrayView1<f64>,
    day_of_year: ArrayView1<usize>,
) -> Result<(), CalibrationError> {
    if precipitation.len() != pet.len() {
        Err(CalibrationError::LengthMismatch(
            precipitation.len(),
            temperature.len(),
            pet.len(),
            day_of_year.len(),
        ))
    } else {
        Ok(())
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
              elevation_layers,
              median_elevation| {
            check_lengths(precipitation, temperature, pet, day_of_year)?;
            if let Some(snow_simulate) = snow_simulate {
                let snow_params = params.slice(s![..n_snow_params]);
                let hydro_params = params.slice(s![n_snow_params..]);

                let effective_precipitation = snow_simulate(
                    snow_params,
                    precipitation,
                    temperature,
                    day_of_year,
                    elevation_layers,
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
                hydro_simulate(params, precipitation, pet)
                    .map_err(CalibrationError::Hydro)
            }
        },
    )
}
