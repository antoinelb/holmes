use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4", "x5", "x6", "x7"];

pub const param_descriptions: &[&str] = &[
    "Surface reservoir capacity (mm)",
    "Intermediate reservoir capacity (mm)",
    "Quadratic routing reservoir capacity (mm)",
    "Groundwater emptying constant (d)",
    "Distribution coefficient (-)",
    "Delay (d)",
    "Intermediate reservoir emptying constant (d)",
];

const BOUNDS: [(&str, f64, f64); 7] = [
    ("x1", 1.0, 2000.0),
    ("x2", 1.0, 2000.0),
    ("x3", 0.01, 1000.0),
    ("x4", 1.0, 500.0),
    ("x5", 0.01, 0.99),
    ("x6", 0.5, 5.0),
    ("x7", 1.0, 500.0),
];

pub fn init() -> (Array1<f64>, Array2<f64>) {
    let bounds = array![
        [BOUNDS[0].1, BOUNDS[0].2],
        [BOUNDS[1].1, BOUNDS[1].2],
        [BOUNDS[2].1, BOUNDS[2].2],
        [BOUNDS[3].1, BOUNDS[3].2],
        [BOUNDS[4].1, BOUNDS[4].2],
        [BOUNDS[5].1, BOUNDS[5].2],
        [BOUNDS[6].1, BOUNDS[6].2],
    ];
    let default_values = bounds.sum_axis(Axis(1)) / 2.0;
    (default_values, bounds)
}

pub fn simulate(
    params: ArrayView1<f64>,
    precipitation: ArrayView1<f64>,
    pet: ArrayView1<f64>,
) -> Result<Array1<f64>, HydroError> {
    let [x1, x2, x3, x4, x5, x6, x7]: [f64; 7] = params
        .as_slice()
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| HydroError::ParamsMismatch(7, params.len()))?;

    for (i, &param_value) in [x1, x2, x3, x4, x5, x6, x7].iter().enumerate() {
        let (name, lower, upper) = BOUNDS[i];
        validate_parameter(param_value, name, lower, upper)?;
    }

    check_lengths(precipitation, pet)?;
    validate_inputs_finite(precipitation, "precipitation")?;
    validate_inputs_finite(pet, "pet")?;
    validate_non_negative(precipitation, "precipitation")?;
    validate_non_negative(pet, "pet")?;

    let mut streamflow: Vec<f64> = vec![0.0; precipitation.len()];

    let (mut s, mut t, mut l, mut r, dl, mut hy) = init_state(x1, x2, x3, x6);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x4, x5, x7, &mut s, &mut t,
                &mut l, &mut r, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "MARTINE simulation")?;

    Ok(result)
}

fn init_state(
    x1: f64,
    x2: f64,
    x3: f64,
    x6: f64,
) -> (f64, f64, f64, f64, Array1<f64>, Array1<f64>) {
    // reservoir state initialization (from HOOPLA ini_HydroMod9.m)
    let s = x1; // surface reservoir starts at full capacity
    let t = x2 * 0.5; // intermediate reservoir starts at half capacity
    let l = 5.0; // groundwater reservoir starts at 5 mm
    let r = x3 * 0.1; // routing reservoir starts at 10% capacity

    // delay vector construction (same pattern as GARDENIA)
    let size = x6.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x6 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

    (s, t, l, r, dl, hy)
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
    x7: f64,
    s: &mut f64,
    t: &mut f64,
    l: &mut f64,
    r: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // surface reservoir (S)
    *s += p;
    let pr = (*s - x1).max(0.0);
    *s -= pr;
    let es = (*s).min(e);
    *s -= es;
    let et = e - es; // remaining ET for intermediate reservoir

    // direct routing reservoir (R) — quadratic emptying
    *r += x5 * pr;
    let qr = (*r * *r) / (*r + x3);
    *r -= qr;

    // intermediate reservoir (T)
    *t = (*t - et).max(0.0); // apply residual ET
    *t += (1.0 - x5) * pr;
    let qt1 = (*t / x7).max(0.0); // linear emptying
    *t -= qt1;
    let qt2 = (*t - x2).max(0.0); // overflow above capacity
    *t -= qt2;

    // groundwater reservoir (L)
    *l += qt1 + qt2;
    let ql = *l / x4;
    *l -= ql;

    // total flow with delay
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * (ql + qr);
    }
    hy[n - 1] = dl[n - 1] * (ql + qr);

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
    let m = PyModule::new(py, "martine")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
