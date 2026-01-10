use crate::pet::utils::{check_lengths, PetError};
use ndarray::{Array1, ArrayView1, Zip};
use numpy::{PyArray1, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;
use std::f64::consts::PI;

pub fn simulate(
    temperature: ArrayView1<f64>,
    day_of_year: ArrayView1<usize>,
    latitude: f64,
) -> Result<Array1<f64>, PetError> {
    check_lengths(temperature, day_of_year)?;

    let gsc = 0.082; // solar constant (MJ m^-2 min^-1)
    let rho = 1000.; // water density (kg/m^3)
    let lat_rad = PI * latitude / 180.; // latitude in rad

    let mut pet: Vec<f64> = vec![0.0; temperature.len()];

    Zip::indexed(&temperature).and(&day_of_year).for_each(
        |t, &temp_t, &doy| {
            let lambda = 2.501 - 0.002361 * temp_t; // latent heat of vaporization (MJ/kg)
            let ds = 0.409 * (2. * PI / 365. * doy as f64 - 1.39).sin(); // solar declination (rad)
            let dr = 1. + 0.033 * (doy as f64 * 2. * PI / 365.).cos(); // inverse relative distance Earth-Sun
            let omega = (-lat_rad.tan() * ds.tan()).clamp(-1., 1.).acos(); // sunset hour angle (rad)
            let re = 24. * 60. / PI
                * gsc
                * dr
                * (omega * lat_rad.sin() * ds.sin()
                    + lat_rad.cos() * ds.cos() * omega.sin()); // extraterrestrial radiation (MJ m^-2 day^-1)
            pet[t] =
                (re / (lambda * rho) * (temp_t + 5.) / 100. * 1000.).max(0.);
        },
    );

    Ok(Array1::from_vec(pet))
}

#[cfg_attr(coverage_nightly, coverage(off))]
#[pyfunction]
#[pyo3(name = "simulate")]
pub fn py_simulate<'py>(
    py: Python<'py>,
    temperature: PyReadonlyArray1<f64>,
    day_of_year: PyReadonlyArray1<usize>,
    latitude: f64,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let simulation =
        simulate(temperature.as_array(), day_of_year.as_array(), latitude)?;
    Ok(simulation.to_pyarray(py))
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "oudin")?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
