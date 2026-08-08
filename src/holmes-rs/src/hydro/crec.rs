use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4", "x5", "x6"];

pub const param_descriptions: &[&str] = &[
    "Surface reservoir emptying constant (d)",
    "Linear percolation parameter (-)",
    "Splitting parameter for raw rainfall (-)",
    "Splitting parameter for PET production (-)",
    "Linear emptying parameter of soil reservoir (-)",
    "Delay parameter (d)",
];

pub const param_descriptions_fr: &[&str] = &[
    "Constante de vidange du réservoir de surface (d)",
    "Paramètre de percolation linéaire (-)",
    "Paramètre de partage de la pluie brute (-)",
    "Paramètre de partage pour la production d'ETP (-)",
    "Paramètre de vidange linéaire du réservoir de sol (-)",
    "Paramètre de délai (d)",
];

const BOUNDS: [(&str, f64, f64); 6] = [
    ("x1", 1.0, 1000.0),
    ("x2", 1.0, 1000.0),
    ("x3", 0.0, 1000.0),
    ("x4", 1.0, 500.0),
    ("x5", 1.0, 1000.0),
    ("x6", 0.5, 5.0),
];

pub fn init() -> (Array1<f64>, Array2<f64>) {
    let bounds = array![
        [BOUNDS[0].1, BOUNDS[0].2],
        [BOUNDS[1].1, BOUNDS[1].2],
        [BOUNDS[2].1, BOUNDS[2].2],
        [BOUNDS[3].1, BOUNDS[3].2],
        [BOUNDS[4].1, BOUNDS[4].2],
        [BOUNDS[5].1, BOUNDS[5].2],
    ];
    let default_values = bounds.sum_axis(Axis(1)) / 2.0;
    (default_values, bounds)
}

pub fn simulate(
    params: ArrayView1<f64>,
    precipitation: ArrayView1<f64>,
    pet: ArrayView1<f64>,
) -> Result<Array1<f64>, HydroError> {
    let [x1, x2, x3, x4, x5, x6]: [f64; 6] = params
        .as_slice()
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| HydroError::ParamsMismatch(6, params.len()))?;

    for (i, &param_value) in [x1, x2, x3, x4, x5, x6].iter().enumerate() {
        let (name, lower, upper) = BOUNDS[i];
        validate_parameter(param_value, name, lower, upper)?;
    }

    check_lengths(precipitation, pet)?;
    validate_inputs_finite(precipitation, "precipitation")?;
    validate_inputs_finite(pet, "pet")?;
    validate_non_negative(precipitation, "precipitation")?;
    validate_non_negative(pet, "pet")?;

    let mut streamflow: Vec<f64> = vec![0.0; precipitation.len()];

    let (mut s, mut r, mut t, xf, dl, mut hy) = init_state(x6);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x4, x5, &mut s, &mut r, &mut t,
                xf, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "CREC simulation")?;

    Ok(result)
}

fn init_state(x6: f64) -> (f64, f64, f64, f64, Array1<f64>, Array1<f64>) {
    // initialization of the reservoir state
    let s = 250.0;
    let r = 10.0;
    let t = 100.0;
    let xf = 245.0;

    let size = x6.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x6 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

    (s, r, t, xf, dl, hy)
}

#[allow(clippy::too_many_arguments)]
fn run_step(
    p: f64,
    e: f64,
    x1: f64,
    x2: f64,
    x3: f64,
    x4: f64,
    x5: f64,
    s: &mut f64,
    r: &mut f64,
    t: &mut f64,
    xf: f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // net inputs
    let p_r = p / (1.0 + ((x3 - *s) / x4).exp());
    let p_s = p - p_r;

    // soil storage (S)
    *s += p_s;
    let e_s = e * (1.0 - (-*s / xf).exp());
    *s = (*s - e_s).max(0.0);

    // surface storage (R)
    *r += p_r;
    let q_r = *r * *r / (*r + x1);
    *r -= q_r;
    let i_r = *r / x5;
    *r -= i_r;

    // groundwter storage (T)
    *t += i_r;
    let q_t = *t / x2;
    *t -= q_t;

    // total flow calculation
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * (q_t + q_r);
    }
    hy[n - 1] = dl[n - 1] * (q_t + q_r);

    hy[0].max(0.0) // simulated streamflow
}

#[cfg_attr(coverage_nightly, coverage(off))]
#[pyfunction]
#[pyo3(name = "init")]
pub fn py_init<'py>(
    py: Python<'py>,
) -> (Bound<'py, PyArray1<f64>>, Bound<'py, PyArray2<f64>>) {
    let (default_values, bounds) = init();
    (default_values.to_pyarray(py), bounds.to_pyarray(py))
}

#[cfg_attr(coverage_nightly, coverage(off))]
#[pyfunction]
#[pyo3(name = "simulate")]
pub fn py_simulate<'py>(
    py: Python<'py>,
    params: PyReadonlyArray1<f64>,
    precipitation: PyReadonlyArray1<f64>,
    pet: PyReadonlyArray1<f64>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let params = params.as_array().to_owned();
    let precipitation = precipitation.as_array().to_owned();
    let pet = pet.as_array().to_owned();
    let simulation = py.detach(|| {
        simulate(params.view(), precipitation.view(), pet.view())
    })?;
    Ok(simulation.to_pyarray(py))
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "crec")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add("param_descriptions_fr", param_descriptions_fr)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
