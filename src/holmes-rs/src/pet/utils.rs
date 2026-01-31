use ndarray::ArrayView1;
use pyo3::prelude::*;
use thiserror::Error;

use crate::errors::{HolmesNumericalError, HolmesValidationError};

#[derive(Error, Debug)]
pub enum PetError {
    #[error(
        "temperature and day_of_year must have the same length (got {0} and {1})"
    )]
    LengthMismatch(usize, usize),
    #[error("Unknown PET model '{0}'")]
    WrongModel(String),
    #[error("Non-finite value in {name} at index {index}: {value}")]
    NonFiniteInput {
        name: &'static str,
        index: usize,
        value: f64,
    },
    #[error("Empty input array: {name}")]
    EmptyInput { name: &'static str },
    #[error(
        "Day of year {value} at index {index} outside valid range [1, 366]"
    )]
    InvalidDayOfYear { index: usize, value: usize },
    #[error("Temperature {value} at index {index} outside physical range [{min}, {max}]")]
    TemperatureOutOfRange {
        index: usize,
        value: f64,
        min: f64,
        max: f64,
    },
    #[error("Latitude {value} outside valid range [{min}, {max}]")]
    LatitudeOutOfRange { value: f64, min: f64, max: f64 },
    #[error("Numerical error in {context}: {detail}")]
    NumericalError {
        context: &'static str,
        detail: String,
    },
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<PetError> for PyErr {
    fn from(err: PetError) -> PyErr {
        match &err {
            PetError::LengthMismatch(_, _)
            | PetError::WrongModel(_)
            | PetError::NonFiniteInput { .. }
            | PetError::EmptyInput { .. }
            | PetError::InvalidDayOfYear { .. }
            | PetError::TemperatureOutOfRange { .. }
            | PetError::LatitudeOutOfRange { .. } => {
                HolmesValidationError::new_err(err.to_string())
            }
            PetError::NumericalError { .. } => {
                HolmesNumericalError::new_err(err.to_string())
            }
        }
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

pub fn validate_temperature(arr: ArrayView1<f64>) -> Result<(), PetError> {
    const min_temp: f64 = -100.0;
    const max_temp: f64 = 100.0;
    if arr.is_empty() {
        return Err(PetError::EmptyInput {
            name: "temperature",
        });
    }
    for (i, &val) in arr.iter().enumerate() {
        if !val.is_finite() {
            return Err(PetError::NonFiniteInput {
                name: "temperature",
                index: i,
                value: val,
            });
        }
        if val < min_temp || val > max_temp {
            return Err(PetError::TemperatureOutOfRange {
                index: i,
                value: val,
                min: min_temp,
                max: max_temp,
            });
        }
    }
    Ok(())
}

pub fn validate_day_of_year(arr: ArrayView1<usize>) -> Result<(), PetError> {
    if arr.is_empty() {
        return Err(PetError::EmptyInput {
            name: "day_of_year",
        });
    }
    for (i, &val) in arr.iter().enumerate() {
        if val < 1 || val > 366 {
            return Err(PetError::InvalidDayOfYear {
                index: i,
                value: val,
            });
        }
    }
    Ok(())
}

pub fn validate_latitude(value: f64) -> Result<(), PetError> {
    const min_lat: f64 = -90.0;
    const max_lat: f64 = 90.0;
    if !value.is_finite() || value < min_lat || value > max_lat {
        return Err(PetError::LatitudeOutOfRange {
            value,
            min: min_lat,
            max: max_lat,
        });
    }
    Ok(())
}

pub fn validate_output(
    arr: ArrayView1<f64>,
    context: &'static str,
) -> Result<(), PetError> {
    for (i, &val) in arr.iter().enumerate() {
        if !val.is_finite() {
            return Err(PetError::NumericalError {
                context,
                detail: format!("non-finite value {} at index {}", val, i),
            });
        }
    }
    Ok(())
}
