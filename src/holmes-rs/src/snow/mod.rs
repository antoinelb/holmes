pub mod cemaneige;
pub mod utils;
use crate::utils::register_submodule;
use pyo3::prelude::*;

pub use utils::{SnowError, SnowInit, SnowSimulate};

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "snow")?;
    register_submodule(py, &m, &cemaneige::make_module(py)?, "hydro_rs.snow")?;
    Ok(m)
}

pub fn get_model(
    model: &str,
) -> Result<(utils::SnowInit, SnowSimulate), SnowError> {
    match model {
        "cemaneige" => Ok((cemaneige::init, cemaneige::simulate)),
        _ => Err(SnowError::WrongModel(model.to_string())),
    }
}
