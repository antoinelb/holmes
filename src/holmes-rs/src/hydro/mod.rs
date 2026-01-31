use pyo3::prelude::*;
pub mod bucket;
pub mod cequeau;
pub mod gr4j;
pub mod utils;
use crate::utils::register_submodule;

pub use utils::{HydroError, HydroInit, HydroSimulate};

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "hydro")?;
    register_submodule(py, &m, &gr4j::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &bucket::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &cequeau::make_module(py)?, "holmes_rs.hydro")?;
    Ok(m)
}

pub fn get_model(
    model: &str,
) -> Result<(utils::HydroInit, HydroSimulate), HydroError> {
    match model {
        "gr4j" => Ok((gr4j::init, gr4j::simulate)),
        "bucket" => Ok((bucket::init, bucket::simulate)),
        "cequeau" => Ok((cequeau::init, cequeau::simulate)),
        _ => Err(HydroError::WrongModel(model.to_string())),
    }
}
