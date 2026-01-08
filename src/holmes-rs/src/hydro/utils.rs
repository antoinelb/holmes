use ndarray::{Array1, Array2, ArrayView1};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use thiserror::Error;

pub type HydroInit = fn() -> (Array1<f64>, Array2<f64>);

pub type HydroSimulate = fn(
    ArrayView1<f64>,
    ArrayView1<f64>,
    ArrayView1<f64>,
) -> Result<Array1<f64>, HydroError>;

#[derive(Error, Debug)]
pub enum HydroError {
    #[error(
        "precipitation and pet must have the same length (got {0} and {1})"
    )]
    LengthMismatch(usize, usize),
    #[error("expected {0} params, got {1}")]
    ParamsMismatch(usize, usize),
    #[error("Unknown model '{0}'. Valid options: gr4j")]
    WrongModel(String),
}

impl From<HydroError> for PyErr {
    fn from(err: HydroError) -> PyErr {
        PyValueError::new_err(err.to_string())
    }
}

pub fn check_lengths(
    precipitation: ArrayView1<f64>,
    pet: ArrayView1<f64>,
) -> Result<(), HydroError> {
    if precipitation.len() != pet.len() {
        Err(HydroError::LengthMismatch(precipitation.len(), pet.len()))
    } else {
        Ok(())
    }
}
