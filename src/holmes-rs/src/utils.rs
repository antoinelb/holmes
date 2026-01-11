use crate::calibration::utils::CalibrationError;
use crate::hydro::HydroError;
use crate::metrics::MetricsError;
use crate::pet::PetError;
use crate::snow::SnowError;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use thiserror::Error;

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn register_submodule(
    py: Python<'_>,
    parent: &Bound<'_, PyModule>,
    child: &Bound<'_, PyModule>,
    parent_path: &str,
) -> PyResult<()> {
    parent.add_submodule(child)?;
    let child_name = child.name()?;
    let full_name = format!("{}.{}", parent_path, child_name);
    py.import("sys")?
        .getattr("modules")?
        .set_item(full_name, child)?;
    Ok(())
}

#[derive(Error, Debug)]
pub enum Error {
    #[error(transparent)]
    Metrics(#[from] MetricsError),
    #[error(transparent)]
    Hydro(#[from] HydroError),
    #[error(transparent)]
    Snow(#[from] SnowError),
    #[error(transparent)]
    Calibration(#[from] CalibrationError),
    #[error(transparent)]
    Pet(#[from] PetError),
}

#[cfg_attr(coverage_nightly, coverage(off))]
impl From<Error> for PyErr {
    fn from(err: Error) -> PyErr {
        PyValueError::new_err(err.to_string())
    }
}
