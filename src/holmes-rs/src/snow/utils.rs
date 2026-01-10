use ndarray::{Array1, Array2, ArrayView1};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use thiserror::Error;

pub type SnowInit = fn() -> (Array1<f64>, Array2<f64>);

pub type SnowSimulate = fn(
    ArrayView1<f64>,
    ArrayView1<f64>,
    ArrayView1<f64>,
    ArrayView1<usize>,
    ArrayView1<f64>,
    f64,
) -> Result<Array1<f64>, SnowError>;

#[derive(Error, Debug)]
pub enum SnowError {
    #[error(
        "precipitation, temperature and day_of_year must have the same length (got {0}, {1} and {2})"
    )]
    LengthMismatch(usize, usize, usize),
    #[error("expected {0} params, got {1}")]
    ParamsMismatch(usize, usize),
    #[error("Unknown model '{0}'. Valid options: cemaneige")]
    WrongModel(String),
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<SnowError> for PyErr {
    fn from(err: SnowError) -> PyErr {
        PyValueError::new_err(err.to_string())
    }
}

pub fn check_lengths(
    precipitation: ArrayView1<f64>,
    temperature: ArrayView1<f64>,
    day_of_year: ArrayView1<usize>,
) -> Result<(), SnowError> {
    if precipitation.len() != temperature.len()
        || precipitation.len() != day_of_year.len()
    {
        Err(SnowError::LengthMismatch(
            precipitation.len(),
            temperature.len(),
            day_of_year.len(),
        ))
    } else {
        Ok(())
    }
}
