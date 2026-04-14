use pyo3::prelude::*;
pub mod bucket;
pub mod cequeau;
pub mod crec;
pub mod gardenia;
pub mod gr4j;
pub mod hbv;
pub mod hymod;
pub mod ihacres;
pub mod martine;
pub mod mohyse;
pub mod mordor;
pub mod nam;
pub mod pdm;
pub mod sacramento;
pub mod simhyd;
pub mod smar;
pub mod tank;
pub mod topmodel;
pub mod utils;
pub mod wageningen;
pub mod xinanjiang;
use crate::utils::register_submodule;

pub use utils::{HydroError, HydroInit, HydroSimulate};

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "hydro")?;
    register_submodule(py, &m, &gr4j::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &bucket::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &cequeau::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &crec::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(
        py,
        &m,
        &gardenia::make_module(py)?,
        "holmes_rs.hydro",
    )?;
    register_submodule(py, &m, &hymod::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &hbv::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &ihacres::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &martine::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &mohyse::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &mordor::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &nam::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &pdm::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(
        py,
        &m,
        &sacramento::make_module(py)?,
        "holmes_rs.hydro",
    )?;
    register_submodule(py, &m, &simhyd::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &smar::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(py, &m, &tank::make_module(py)?, "holmes_rs.hydro")?;
    register_submodule(
        py,
        &m,
        &topmodel::make_module(py)?,
        "holmes_rs.hydro",
    )?;
    register_submodule(
        py,
        &m,
        &wageningen::make_module(py)?,
        "holmes_rs.hydro",
    )?;
    register_submodule(
        py,
        &m,
        &xinanjiang::make_module(py)?,
        "holmes_rs.hydro",
    )?;
    Ok(m)
}

pub fn get_model(
    model: &str,
) -> Result<(utils::HydroInit, HydroSimulate), HydroError> {
    match model {
        "gr4j" => Ok((gr4j::init, gr4j::simulate)),
        "bucket" => Ok((bucket::init, bucket::simulate)),
        "cequeau" => Ok((cequeau::init, cequeau::simulate)),
        "crec" => Ok((crec::init, crec::simulate)),
        "gardenia" => Ok((gardenia::init, gardenia::simulate)),
        "hymod" => Ok((hymod::init, hymod::simulate)),
        "hbv" => Ok((hbv::init, hbv::simulate)),
        "ihacres" => Ok((ihacres::init, ihacres::simulate)),
        "martine" => Ok((martine::init, martine::simulate)),
        "mohyse" => Ok((mohyse::init, mohyse::simulate)),
        "mordor" => Ok((mordor::init, mordor::simulate)),
        "nam" => Ok((nam::init, nam::simulate)),
        "pdm" => Ok((pdm::init, pdm::simulate)),
        "sacramento" => Ok((sacramento::init, sacramento::simulate)),
        "simhyd" => Ok((simhyd::init, simhyd::simulate)),
        "smar" => Ok((smar::init, smar::simulate)),
        "tank" => Ok((tank::init, tank::simulate)),
        "topmodel" => Ok((topmodel::init, topmodel::simulate)),
        "wageningen" => Ok((wageningen::init, wageningen::simulate)),
        "xinanjiang" => Ok((xinanjiang::init, xinanjiang::simulate)),
        _ => Err(HydroError::WrongModel(model.to_string())),
    }
}
