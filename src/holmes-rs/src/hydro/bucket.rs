use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4", "x5", "x6"];

pub const param_descriptions: &[&str] = &[
    "Soil reservoir capacity (mm)",
    "Evapotranspiration fraction (-)",
    "Runoff delay constant (d)",
    "Non-linearity exponent (-)",
    "Percolation fraction (-)",
    "Transfer delay constant (d)",
];

const BOUNDS: [(&str, f64, f64); 6] = [
    ("x1", 10.0, 1000.0),
    ("x2", 0.0, 1.0),
    ("x3", 1.0, 200.0),
    ("x4", 2.0, 10.0),
    ("x5", 0.0, 1.0),
    ("x6", 1.0, 400.0),
];

pub fn init() -> (Array1<f64>, Array2<f64>) {
    // corresponds to x1, x2, x3, x4, x5, x6
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

    let (mut s, mut r, mut t, mut dl, mut hy) =
        initialize_state(x1, x4);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x5, x6, &mut s, &mut r,
                &mut t, &mut dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "Bucket simulation")?;

    Ok(result)
}

fn initialize_state(
    x1: f64,
    x4: f64,
) -> (f64, f64, f64, Array1<f64>, Array1<f64>) {
    // initialization of the reservoir state
    let s = x1 * 0.5;
    let r = 10.0;
    let t = 5.0;

    // array of ints from 0 to the routing delay
    let n = x4.ceil() as usize;
    let k = Array1::from_iter(0..n);

    let mut dl = Array1::zeros(x4.ceil() as usize);
    dl[n - 2] = 1.0 / (x4 - k[n - 1] as f64 + 1.0);
    dl[n - 1] = 1.0 - dl[n - 2];

    let hy = Array1::zeros(x4.ceil() as usize);

    (s, r, t, dl, hy)
}

#[allow(clippy::too_many_arguments)]
fn run_step(
    p: f64,
    e: f64,
    x1: f64,
    x2: f64,
    x3: f64,
    x5: f64,
    x6: f64,
    s: &mut f64,
    r: &mut f64,
    t: &mut f64,
    dl: &mut Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // slow flow precipitation
    let p_s = (1.0 - x5) * p;
    // fast flow precipitation
    let p_r = x5 * p;

    // soil moisture accounting
    let mut i_s = 0.0;
    if p_s >= e {
        *s += p_s - e;
        i_s = (*s - x1).max(0.0);
        *s -= i_s;
    } else {
        // dry conditions
        *s *= ((p_s - e) / x1).exp();
    }

    // slow routing component
    *r += i_s * (1.0 - x2);
    let q_r = *r / (x3 * x6);
    *r -= q_r;

    // fast routing component
    *t += p_r + i_s * x2;
    let q_t = *t / x6;
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
    let simulation =
        simulate(params.as_array(), precipitation.as_array(), pet.as_array())?;
    Ok(simulation.to_pyarray(py))
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "bucket")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
