use pyo3::prelude::*;
pub mod oudin;
mod utils;
use crate::utils::register_submodule;

pub use utils::PetError;

pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "pet")?;
    register_submodule(py, &m, &oudin::make_module(py)?, "holmes_rs.pet")?;
    Ok(m)
}
