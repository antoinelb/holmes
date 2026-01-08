use ndarray::ArrayView1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum PetError {
    #[error(
        "temperature and day_of_year must have the same length (got {0} and {1})"
    )]
    LengthMismatch(usize, usize),
    #[error("Unknown model '{0}'. Valid options: gr4j")]
    WrongModel(String),
}

impl From<PetError> for PyErr {
    fn from(err: PetError) -> PyErr {
        PyValueError::new_err(err.to_string())
    }
}

pub fn check_lengths(
    temperature: ArrayView1<f64>,
    day_of_year: ArrayView1<usize>,
) -> Result<(), PetError> {
    if temperature.len() != day_of_year.len() {
        Err(PetError::LengthMismatch(
            temperature.len(),
            day_of_year.len(),
        ))
    } else {
        Ok(())
    }
}
