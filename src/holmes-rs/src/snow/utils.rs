use ndarray::{Array1, Array2, ArrayView1};
use pyo3::prelude::*;
use thiserror::Error;

use crate::errors::{HolmesNumericalError, HolmesValidationError};

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
    #[error("Unknown snow model '{0}'")]
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
    #[error("Numerical error in {context}: {detail}")]
    NumericalError {
        context: &'static str,
        detail: String,
    },
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<SnowError> for PyErr {
    fn from(err: SnowError) -> PyErr {
        match &err {
            SnowError::LengthMismatch(_, _, _)
            | SnowError::ParamsMismatch(_, _)
            | SnowError::WrongModel(_)
            | SnowError::ParameterOutOfBounds { .. }
            | SnowError::NegativeInput { .. }
            | SnowError::NonFiniteInput { .. }
            | SnowError::EmptyInput { .. }
            | SnowError::InvalidDayOfYear { .. }
            | SnowError::TemperatureOutOfRange { .. } => {
                HolmesValidationError::new_err(err.to_string())
            }
            SnowError::NumericalError { .. } => {
                HolmesNumericalError::new_err(err.to_string())
            }
        }
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

pub fn validate_inputs_finite(
    arr: ArrayView1<f64>,
    name: &'static str,
) -> Result<(), SnowError> {
    if arr.is_empty() {
        return Err(SnowError::EmptyInput { name });
    }
    for (i, &val) in arr.iter().enumerate() {
        if !val.is_finite() {
            return Err(SnowError::NonFiniteInput {
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
) -> Result<(), SnowError> {
    for (i, &val) in arr.iter().enumerate() {
        if val < 0.0 {
            return Err(SnowError::NegativeInput {
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
) -> Result<(), SnowError> {
    if !value.is_finite() || value < lower || value > upper {
        return Err(SnowError::ParameterOutOfBounds {
            name,
            value,
            lower,
            upper,
        });
    }
    Ok(())
}

pub fn validate_temperature(arr: ArrayView1<f64>) -> Result<(), SnowError> {
    const min_temp: f64 = -100.0;
    const max_temp: f64 = 100.0;
    validate_inputs_finite(arr, "temperature")?;
    for (i, &val) in arr.iter().enumerate() {
        if val < min_temp || val > max_temp {
            return Err(SnowError::TemperatureOutOfRange {
                index: i,
                value: val,
                min: min_temp,
                max: max_temp,
            });
        }
    }
    Ok(())
}

pub fn validate_day_of_year(arr: ArrayView1<usize>) -> Result<(), SnowError> {
    if arr.is_empty() {
        return Err(SnowError::EmptyInput {
            name: "day_of_year",
        });
    }
    for (i, &val) in arr.iter().enumerate() {
        if val < 1 || val > 366 {
            return Err(SnowError::InvalidDayOfYear {
                index: i,
                value: val,
            });
        }
    }
    Ok(())
}

pub fn validate_output(
    arr: ArrayView1<f64>,
    context: &'static str,
) -> Result<(), SnowError> {
    for (i, &val) in arr.iter().enumerate() {
        if !val.is_finite() {
            return Err(SnowError::NumericalError {
                context,
                detail: format!("non-finite value {} at index {}", val, i),
            });
        }
    }
    Ok(())
}
