use crate::hydro::utils::{check_lengths, HydroError};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] =
    &["c_soil", "alpha", "k_r", "delta", "beta", "k_t"];

pub fn init() -> (Array1<f64>, Array2<f64>) {
    // corresponds to c_soil, alpha, k_r, delta, beta, k_t
    let bounds = array![
        [10.0, 1000.0],
        [0.0, 1.0],
        [1.0, 200.0],
        [2.0, 10.0],
        [0.0, 1.0],
        [1.0, 400.0]
    ];
    let default_values = bounds.sum_axis(Axis(1)) / 2.0;
    (default_values, bounds)
}

pub fn simulate(
    params: ArrayView1<f64>,
    precipitation: ArrayView1<f64>,
    pet: ArrayView1<f64>,
) -> Result<Array1<f64>, HydroError> {
    let [c_soil, alpha, k_r, delta, beta, k_t]: [f64; 6] = params
        .as_slice()
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| HydroError::ParamsMismatch(6, params.len()))?;
    check_lengths(precipitation, pet)?;

    let mut streamflow: Vec<f64> = vec![0.0; precipitation.len()];

    let (mut s, mut r, mut t, mut dl, mut hy) =
        initialize_state(c_soil, delta);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, c_soil, alpha, k_r, beta, k_t, &mut s,
                &mut r, &mut t, &mut dl, &mut hy,
            );
        });

    Ok(Array1::from_vec(streamflow))
}

fn initialize_state(
    c_soil: f64,
    delta: f64,
) -> (f64, f64, f64, Array1<f64>, Array1<f64>) {
    // initialization of the reservoir state
    let s = c_soil * 0.5;
    let r = 10.0;
    let t = 5.0;

    // array of ints from 0 to the routing delay
    let n = delta.ceil() as usize;
    let k = Array1::from_iter(0..n);

    let mut dl = Array1::zeros(delta.ceil() as usize);
    dl[n - 2] = 1.0 / (delta - k[n - 1] as f64 + 1.0);
    dl[n - 1] = 1.0 - dl[n - 2];

    let hy = Array1::zeros(delta.ceil() as usize);

    (s, r, t, dl, hy)
}

#[allow(clippy::too_many_arguments)]
fn run_step(
    p: f64,
    e: f64,
    c_soil: f64,
    alpha: f64,
    k_r: f64,
    beta: f64,
    k_t: f64,
    s: &mut f64,
    r: &mut f64,
    t: &mut f64,
    dl: &mut Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // slow flow precipitation
    let p_s = (1.0 - beta) * p;
    // fast flow precipitation
    let p_r = beta * p;

    // soil moisture accounting
    let mut i_s = 0.0;
    if p_s >= e {
        *s += p_s - e;
        i_s = (*s - c_soil).max(0.0);
        *s -= i_s;
    } else {
        // dry conditions
        *s *= ((p_s - e) / c_soil).exp();
    }

    // slow routing component
    *r += i_s * (1.0 - alpha);
    let q_r = *r / (k_r * k_t);
    *r -= q_r;

    // fast routing component
    *t += p_r + i_s * alpha;
    let q_t = *t / k_t;
    *t -= q_t;

    // total flow calculation
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * (q_t + q_r);
    }
    hy[n - 1] = dl[n - 1] * (q_t + q_r);

    hy[0].max(0.0) // simulated streamflow
}

#[pyfunction]
#[pyo3(name = "init")]
pub fn py_init<'py>(
    py: Python<'py>,
) -> (Bound<'py, PyArray1<f64>>, Bound<'py, PyArray2<f64>>) {
    let (default_values, bounds) = init();
    (default_values.to_pyarray(py), bounds.to_pyarray(py))
}

#[pyfunction]
#[pyo3(name = "simulate")]
pub fn py_simulate<'py>(
    py: Python<'py>,
    params: PyReadonlyArray1<f64>,
    precipitation: PyReadonlyArray1<f64>,
    pet: PyReadonlyArray1<f64>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let simulation =
        simulate(params.as_array(), precipitation.as_array(), pet.as_array())?;
    Ok(simulation.to_pyarray(py))
}

pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "bucket")?;
    m.add("param_names", param_names)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
