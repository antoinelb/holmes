use ndarray::{Array1, Array2, ArrayView1};
use pyo3::prelude::*;
use thiserror::Error;

use crate::errors::{HolmesNumericalError, HolmesValidationError};

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
    #[error("Unknown model '{0}'. Valid options: gr4j, bucket")]
    WrongModel(String),
    #[error(
        "Parameter '{name}' value {value} outside bounds [{lower}, {upper}]"
    )]
    ParameterOutOfBounds {
        name: &'static str,
        value: f64,
        lower: f64,
        upper: f64,
    },
    #[error("Negative value in {name} at index {index}: {value}")]
    NegativeInput {
        name: &'static str,
        index: usize,
        value: f64,
    },
    #[error("Non-finite value in {name} at index {index}: {value}")]
    NonFiniteInput {
        name: &'static str,
        index: usize,
        value: f64,
    },
    #[error("Empty input array: {name}")]
    EmptyInput { name: &'static str },
    #[error("Numerical error in {context}: {detail}")]
    NumericalError {
        context: &'static str,
        detail: String,
    },
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<HydroError> for PyErr {
    fn from(err: HydroError) -> PyErr {
        match &err {
            HydroError::LengthMismatch(_, _)
            | HydroError::ParamsMismatch(_, _)
            | HydroError::WrongModel(_)
            | HydroError::ParameterOutOfBounds { .. }
            | HydroError::NegativeInput { .. }
            | HydroError::NonFiniteInput { .. }
            | HydroError::EmptyInput { .. } => {
                HolmesValidationError::new_err(err.to_string())
            }
            HydroError::NumericalError { .. } => {
                HolmesNumericalError::new_err(err.to_string())
            }
        }
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

pub fn validate_inputs_finite(
    arr: ArrayView1<f64>,
    name: &'static str,
) -> Result<(), HydroError> {
    if arr.is_empty() {
        return Err(HydroError::EmptyInput { name });
    }
    for (i, &val) in arr.iter().enumerate() {
        if !val.is_finite() {
            return Err(HydroError::NonFiniteInput {
                name,
                index: i,
                value: val,
            });
        }
    }
    Ok(())
}

pub fn validate_non_negative(
    arr: ArrayView1<f64>,
    name: &'static str,
) -> Result<(), HydroError> {
    for (i, &val) in arr.iter().enumerate() {
        if val < 0.0 {
            return Err(HydroError::NegativeInput {
                name,
                index: i,
                value: val,
            });
        }
    }
    Ok(())
}

pub fn validate_parameter(
    value: f64,
    name: &'static str,
    lower: f64,
    upper: f64,
) -> Result<(), HydroError> {
    if !value.is_finite() || value < lower || value > upper {
        return Err(HydroError::ParameterOutOfBounds {
            name,
            value,
            lower,
            upper,
        });
    }
    Ok(())
}

pub fn validate_output(
    arr: ArrayView1<f64>,
    context: &'static str,
) -> Result<(), HydroError> {
    for (i, &val) in arr.iter().enumerate() {
        if !val.is_finite() {
            return Err(HydroError::NumericalError {
                context,
                detail: format!("non-finite value {} at index {}", val, i),
            });
        }
    }
    Ok(())
}
