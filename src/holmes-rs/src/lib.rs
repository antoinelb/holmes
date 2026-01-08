#![allow(non_upper_case_globals)]
mod calibration;
mod hydro;
mod metrics;
mod pet;
mod snow;
mod utils;

use pyo3::prelude::*;
use utils::register_submodule;

#[pymodule]
fn holmes_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();

    register_submodule(py, m, &calibration::make_module(py)?, "holmes_rs")?;
    register_submodule(py, m, &hydro::make_module(py)?, "holmes_rs")?;
    register_submodule(py, m, &metrics::make_module(py)?, "holmes_rs")?;
    register_submodule(py, m, &pet::make_module(py)?, "holmes_rs")?;
    register_submodule(py, m, &snow::make_module(py)?, "holmes_rs")?;

    m.add("__version__", env!("CARGO_PKG_VERSION"))?;

    Ok(())
}
