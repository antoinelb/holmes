use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4", "x5", "x6", "x7"];

pub const param_descriptions: &[&str] = &[
    "Upper outflow threshold of surface reservoir (mm)",
    "Lower outflow threshold (mm)",
    "Fast emptying constant of surface reservoir (d)",
    "Intermediate emptying multiplier of upper soil reservoir (-)",
    "Delay (d)",
    "PET correction coefficient (-)",
    "Slow emptying multiplier of lower soil reservoir (-)",
];

// Lower bounds on x3, x4, x7 are >= 1 so every linear drain (q = storage
// divided by the product of these factors) never exceeds its storage,
// keeping all four reservoirs non-negative by construction.
const BOUNDS: [(&str, f64, f64); 7] = [
    ("x1", 1.0, 1000.0),
    ("x2", 1.0, 1000.0),
    ("x3", 1.0, 100.0),
    ("x4", 1.0, 100.0),
    ("x5", 0.5, 5.0),
    ("x6", 0.1, 2.0),
    ("x7", 1.0, 100.0),
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

    let (mut s, mut r, mut t, mut l, dl, mut hy) = init_state(x5);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x4, x6, x7, &mut s, &mut r,
                &mut t, &mut l, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "TANK simulation")?;

    Ok(result)
}

fn init_state(x5: f64) -> (f64, f64, f64, f64, Array1<f64>, Array1<f64>) {
    // initial reservoir states follow HOOPLA HM17 (all four set to 10 mm)
    let s = 10.0;
    let r = 10.0;
    let t = 10.0;
    let l = 10.0;

    let size = x5.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x5 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

    (s, r, t, l, dl, hy)
}

#[allow(clippy::too_many_arguments)]
fn run_step(
    p: f64,
    e: f64,
    x1: f64,
    x2: f64,
    x3: f64,
    x4: f64,
    x6: f64,
    x7: f64,
    s: &mut f64,
    r: &mut f64,
    t: &mut f64,
    l: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // surface reservoir (S) — two side outlets above thresholds, bottom drain, ETP
    *s += p;
    let e1 = e * x6;
    let qs1 = ((*s - (x1 + x2)) / x3).max(0.0);
    *s -= qs1;
    let qs2 = ((*s - x2) / x3).max(0.0);
    *s -= qs2;
    let is = *s / x3;
    *s -= is;
    let es = e1.min(*s);
    *s -= es;
    let e2 = e1 - es;

    // upper soil reservoir (R)
    *r += is;
    let qr = ((*r - x2) / (x3 * x4)).max(0.0);
    *r -= qr;
    let ir = *r / (x3 * x4);
    *r -= ir;
    let er = e2.min(*r);
    *r -= er;
    let e3 = e2 - er;

    // lower soil reservoir (T)
    *t += ir;
    let qt = ((*t - x2) / (x3 * x4 * x7)).max(0.0);
    *t -= qt;
    let it = *t / (x3 * x4 * x7);
    *t -= it;
    let et = e3.min(*t);
    *t -= et;
    let e4 = e3 - et;

    // groundwater reservoir (L) — quadratic emptying via x7^2
    *l += it;
    let ql = *l / (x3 * x4 * x7 * x7);
    *l -= ql;
    let el = e4.min(*l);
    *l -= el;

    // delay routing on the sum of all five outflows
    let total = qs1 + qs2 + qr + qt + ql;
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * total;
    }
    hy[n - 1] = dl[n - 1] * total;

    hy[0].max(0.0)
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
    let m = PyModule::new(py, "tank")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
