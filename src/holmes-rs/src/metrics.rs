use ndarray::ArrayView1;
use numpy::PyReadonlyArray1;
use pyo3::prelude::*;
use thiserror::Error;

use crate::errors::{HolmesNumericalError, HolmesValidationError};

const TOLERANCE: f64 = 1e-10;

/// Validate that a computed result is finite, returning an error otherwise.
pub fn validate_result(
    value: f64,
    context: &'static str,
    detail: String,
) -> Result<f64, MetricsError> {
    if !value.is_finite() {
        return Err(MetricsError::NumericalError { context, detail });
    }
    Ok(value)
}

#[derive(Error, Debug)]
pub enum MetricsError {
    #[error("observations and simulations must have the same length (got {0} and {1})")]
    LengthMismatch(usize, usize),

    #[error("Empty input arrays")]
    EmptyArrays,

    #[error("NaN found in {array_name} at index {index}")]
    NaNInInput {
        array_name: &'static str,
        index: usize,
    },

    #[error("Infinity found in {array_name} at index {index}")]
    InfinityInInput {
        array_name: &'static str,
        index: usize,
    },

    #[error("Zero variance in observations - NSE undefined for constant observations")]
    ZeroVarianceNSE,

    #[error("Zero variance in {component} - KGE undefined")]
    ZeroVarianceKGE { component: &'static str },

    #[error("Zero mean in observations - KGE beta component undefined")]
    ZeroMeanKGE,

    #[error("Numerical error in {context}: {detail}")]
    NumericalError {
        context: &'static str,
        detail: String,
    },
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<MetricsError> for PyErr {
    fn from(err: MetricsError) -> PyErr {
        match &err {
            // Validation errors
            MetricsError::LengthMismatch(_, _)
            | MetricsError::EmptyArrays
            | MetricsError::NaNInInput { .. }
            | MetricsError::InfinityInInput { .. } => {
                HolmesValidationError::new_err(err.to_string())
            }
            // Numerical errors
            MetricsError::ZeroVarianceNSE
            | MetricsError::ZeroVarianceKGE { .. }
            | MetricsError::ZeroMeanKGE
            | MetricsError::NumericalError { .. } => {
                HolmesNumericalError::new_err(err.to_string())
            }
        }
    }
}

fn validate_inputs(
    observations: ArrayView1<f64>,
    simulations: ArrayView1<f64>,
) -> Result<(), MetricsError> {
    check_lengths(observations, simulations)?;

    if observations.is_empty() {
        return Err(MetricsError::EmptyArrays);
    }

    for (i, &val) in observations.iter().enumerate() {
        if val.is_nan() {
            return Err(MetricsError::NaNInInput {
                array_name: "observations",
                index: i,
            });
        }
        if val.is_infinite() {
            return Err(MetricsError::InfinityInInput {
                array_name: "observations",
                index: i,
            });
        }
    }

    for (i, &val) in simulations.iter().enumerate() {
        if val.is_nan() {
            return Err(MetricsError::NaNInInput {
                array_name: "simulations",
                index: i,
            });
        }
        if val.is_infinite() {
            return Err(MetricsError::InfinityInInput {
                array_name: "simulations",
                index: i,
            });
        }
    }

    Ok(())
}

pub fn calculate_rmse(
    observations: ArrayView1<f64>,
    simulations: ArrayView1<f64>,
) -> Result<f64, MetricsError> {
    validate_inputs(observations, simulations)?;

    let sum: f64 = observations
        .iter()
        .zip(simulations)
        .map(|(o, p)| (o - p).powi(2))
        .sum();

    let rmse = (sum / observations.len() as f64).sqrt();

    validate_result(rmse, "RMSE calculation", format!("result is {}", rmse))
}

pub fn calculate_nse(
    observations: ArrayView1<f64>,
    simulations: ArrayView1<f64>,
) -> Result<f64, MetricsError> {
    validate_inputs(observations, simulations)?;

    let mean: f64 =
        observations.iter().sum::<f64>() / observations.len() as f64;
    let (numerator, denominator) = observations.iter().zip(simulations).fold(
        (0.0, 0.0),
        |(num, den), (&o, &p)| {
            (num + (o - p).powi(2), den + (o - mean).powi(2))
        },
    );

    if denominator < TOLERANCE {
        return Err(MetricsError::ZeroVarianceNSE);
    }

    let nse = 1.0 - numerator / denominator;

    validate_result(
        nse,
        "NSE calculation",
        format!(
            "numerator={}, denominator={}, result={}",
            numerator, denominator, nse
        ),
    )
}

pub fn calculate_kge(
    observations: ArrayView1<f64>,
    simulations: ArrayView1<f64>,
) -> Result<f64, MetricsError> {
    validate_inputs(observations, simulations)?;

    let n = observations.len() as f64;
    let observations_mean = observations.iter().sum::<f64>() / n;
    let observations_mean_2 =
        observations.iter().map(|x| x.powi(2)).sum::<f64>() / n;
    let simulations_mean = simulations.iter().sum::<f64>() / n;
    let simulations_mean_2 =
        simulations.iter().map(|x| x.powi(2)).sum::<f64>() / n;
    let observations_simulations_mean = observations
        .iter()
        .zip(simulations)
        .map(|(o, p)| o * p)
        .sum::<f64>()
        / n;

    let obs_var = observations_mean_2 - observations_mean.powi(2);
    if obs_var < TOLERANCE {
        return Err(MetricsError::ZeroVarianceKGE {
            component: "observations",
        });
    }
    let observations_std = obs_var.sqrt();

    let sim_var = simulations_mean_2 - simulations_mean.powi(2);
    if sim_var < TOLERANCE {
        return Err(MetricsError::ZeroVarianceKGE {
            component: "simulations",
        });
    }
    let simulations_std = sim_var.sqrt();

    let covariance =
        observations_simulations_mean - observations_mean * simulations_mean;

    // std_product is guaranteed >= TOLERANCE since both stds passed their individual checks
    let std_product = observations_std * simulations_std;
    let r: f64 = covariance / std_product;

    let alpha: f64 = simulations_std / observations_std;

    if observations_mean.abs() < TOLERANCE {
        return Err(MetricsError::ZeroMeanKGE);
    }
    let beta: f64 = simulations_mean / observations_mean;

    let kge = 1.0
        - ((r - 1.).powi(2) + (alpha - 1.).powi(2) + (beta - 1.).powi(2))
            .sqrt();

    validate_result(
        kge,
        "KGE calculation",
        format!("r={}, alpha={}, beta={}, result={}", r, alpha, beta, kge),
    )
}

fn check_lengths(
    observations: ArrayView1<f64>,
    simulations: ArrayView1<f64>,
) -> Result<(), MetricsError> {
    if observations.len() != simulations.len() {
        Err(MetricsError::LengthMismatch(
            observations.len(),
            simulations.len(),
        ))
    } else {
        Ok(())
    }
}

#[cfg_attr(coverage_nightly, coverage(off))]
#[pyfunction]
#[pyo3(name = "calculate_rmse")]
pub fn py_calculate_rmse<'py>(
    observations: PyReadonlyArray1<'py, f64>,
    simulations: PyReadonlyArray1<'py, f64>,
) -> PyResult<f64> {
    Ok(calculate_rmse(
        observations.as_array(),
        simulations.as_array(),
    )?)
}

#[cfg_attr(coverage_nightly, coverage(off))]
#[pyfunction]
#[pyo3(name = "calculate_nse")]
pub fn py_calculate_nse<'py>(
    observations: PyReadonlyArray1<'py, f64>,
    simulations: PyReadonlyArray1<'py, f64>,
) -> PyResult<f64> {
    Ok(calculate_nse(
        observations.as_array(),
        simulations.as_array(),
    )?)
}

#[cfg_attr(coverage_nightly, coverage(off))]
#[pyfunction]
#[pyo3(name = "calculate_kge")]
pub fn py_calculate_kge<'py>(
    observations: PyReadonlyArray1<'py, f64>,
    simulations: PyReadonlyArray1<'py, f64>,
) -> PyResult<f64> {
    Ok(calculate_kge(
        observations.as_array(),
        simulations.as_array(),
    )?)
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "metrics")?;
    m.add_function(wrap_pyfunction!(py_calculate_rmse, &m)?)?;
    m.add_function(wrap_pyfunction!(py_calculate_nse, &m)?)?;
    m.add_function(wrap_pyfunction!(py_calculate_kge, &m)?)?;
    Ok(m)
}
