pub mod sce;
pub mod utils;

use crate::utils::register_submodule;
use pyo3::prelude::*;

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "calibration")?;
    register_submodule(
        py,
        &m,
        &sce::make_module(py)?,
        "holmes_rs.calibration",
    )?;
    Ok(m)
}
