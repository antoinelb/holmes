use pyo3::prelude::*;
pub mod gr4j;
mod utils;
use crate::utils::register_submodule;

pub use utils::{HydroError, HydroSimulate};

pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "hydro")?;
    register_submodule(py, &m, &gr4j::make_module(py)?, "holmes_rs.hydro")?;
    Ok(m)
}

pub fn get_model(
    model: &str,
) -> Result<(utils::HydroInit, HydroSimulate), HydroError> {
    match model {
        "gr4j" => Ok((gr4j::init, gr4j::simulate)),
        _ => Err(HydroError::WrongModel(model.to_string())),
    }
}
