use pyo3::create_exception;
use pyo3::prelude::*;
use thiserror::Error;

create_exception!(holmes_rs, HolmesError, pyo3::exceptions::PyException);
create_exception!(holmes_rs, HolmesNumericalError, HolmesError);
create_exception!(holmes_rs, HolmesValidationError, HolmesError);

#[derive(Error, Debug)]
pub enum NumericalError {
    #[error("Division by zero in {context}: {detail}")]
    DivisionByZero {
        context: &'static str,
        detail: String,
    },

    #[error("NaN detected in {context}: {detail}")]
    NaNDetected {
        context: &'static str,
        detail: String,
    },

    #[error("Infinity detected in {context}: {detail}")]
    InfinityDetected {
        context: &'static str,
        detail: String,
    },

    #[error("Negative sqrt argument in {context}: value={value}")]
    NegativeSqrt { context: &'static str, value: f64 },

    #[error("Zero variance in {context}: all values are constant")]
    ZeroVariance { context: &'static str },
}

#[derive(Error, Debug)]
pub enum ValidationError {
    #[error(
        "Parameter '{name}' value {value} outside bounds [{lower}, {upper}]"
    )]
    ParameterOutOfBounds {
        name: &'static str,
        value: f64,
        lower: f64,
        upper: f64,
    },

    #[error("Negative precipitation at index {index}: value={value}")]
    NegativePrecipitation { index: usize, value: f64 },

    #[error("Temperature {value} at index {index} outside physical range [{min}, {max}]")]
    TemperatureOutOfRange {
        index: usize,
        value: f64,
        min: f64,
        max: f64,
    },

    #[error(
        "Day of year {value} at index {index} outside valid range [1, 366]"
    )]
    InvalidDayOfYear { index: usize, value: usize },

    #[error("Empty input array: {name}")]
    EmptyArray { name: &'static str },

    #[error("NaN found in input array '{name}' at index {index}")]
    NaNInInput { name: &'static str, index: usize },

    #[error("Infinity found in input array '{name}' at index {index}")]
    InfinityInInput { name: &'static str, index: usize },
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<NumericalError> for PyErr {
    fn from(err: NumericalError) -> PyErr {
        HolmesNumericalError::new_err(err.to_string())
    }
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<ValidationError> for PyErr {
    fn from(err: ValidationError) -> PyErr {
        HolmesValidationError::new_err(err.to_string())
    }
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn register_exceptions(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("HolmesError", m.py().get_type::<HolmesError>())?;
    m.add(
        "HolmesNumericalError",
        m.py().get_type::<HolmesNumericalError>(),
    )?;
    m.add(
        "HolmesValidationError",
        m.py().get_type::<HolmesValidationError>(),
    )?;
    Ok(())
}
