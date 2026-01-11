#![allow(non_upper_case_globals)]
#![cfg_attr(coverage_nightly, feature(coverage_attribute))]
pub mod calibration;
pub mod errors;
pub mod hydro;
pub mod metrics;
pub mod pet;
pub mod snow;
mod utils;

use pyo3::prelude::*;
use utils::register_submodule;

#[cfg_attr(coverage_nightly, coverage(off))]
#[pymodule]
fn holmes_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();

    errors::register_exceptions(m)?;

    register_submodule(py, m, &calibration::make_module(py)?, "holmes_rs")?;
    register_submodule(py, m, &hydro::make_module(py)?, "holmes_rs")?;
    register_submodule(py, m, &metrics::make_module(py)?, "holmes_rs")?;
    register_submodule(py, m, &pet::make_module(py)?, "holmes_rs")?;
    register_submodule(py, m, &snow::make_module(py)?, "holmes_rs")?;

    m.add("__version__", env!("CARGO_PKG_VERSION"))?;

    Ok(())
}
