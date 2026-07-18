use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] =
    &["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"];

pub const param_descriptions: &[&str] = &[
    "Interception store capacity (mm)",
    "Soil moisture store capacity (mm)",
    "Ground reservoir emptying constant (-)",
    "Delay (d)",
    "Routing reservoir emptying constant (d)",
    "Interflow constant (-)",
    "Groundwater recharge constant (-)",
    "Maximum infiltration capacity (mm)",
];

const BOUNDS: [(&str, f64, f64); 8] = [
    ("x1", 0.5, 10.0),
    ("x2", 1.0, 500.0),
    ("x3", 1.0, 1000.0),
    ("x4", 0.5, 5.0),
    ("x5", 1.0, 500.0),
    ("x6", 1.0, 1000.0),
    ("x7", 1.0, 1000.0),
    ("x8", 1.0, 500.0),
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
        [BOUNDS[7].1, BOUNDS[7].2],
    ];
    let default_values = bounds.sum_axis(Axis(1)) / 2.0;
    (default_values, bounds)
}

pub fn simulate(
    params: ArrayView1<f64>,
    precipitation: ArrayView1<f64>,
    pet: ArrayView1<f64>,
) -> Result<Array1<f64>, HydroError> {
    let [x1, x2, x3, x4, x5, x6, x7, x8]: [f64; 8] = params
        .as_slice()
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| HydroError::ParamsMismatch(8, params.len()))?;

    for (i, &param_value) in
        [x1, x2, x3, x4, x5, x6, x7, x8].iter().enumerate()
    {
        let (name, lower, upper) = BOUNDS[i];
        validate_parameter(param_value, name, lower, upper)?;
    }

    check_lengths(precipitation, pet)?;
    validate_inputs_finite(precipitation, "precipitation")?;
    validate_inputs_finite(pet, "pet")?;
    validate_non_negative(precipitation, "precipitation")?;
    validate_non_negative(pet, "pet")?;

    let mut streamflow: Vec<f64> = vec![0.0; precipitation.len()];

    let (mut s, mut r, mut t, dl, mut hy) = init_state(x2, x4);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x5, x6, x7, x8, &mut s, &mut r,
                &mut t, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "SIMHYD simulation")?;

    Ok(result)
}

fn init_state(x2: f64, x4: f64) -> (f64, f64, f64, Array1<f64>, Array1<f64>) {
    let s = x2 * 0.5;
    let r = 80.0;
    let t = 1.0;

    let size = x4.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x4 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

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
    x7: f64,
    x8: f64,
    s: &mut f64,
    r: &mut f64,
    t: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // --- Interception ---
    // Limited by both interception capacity (x1) and available PET
    let cap = p.min(x1.min(e));
    let (exc, e1) = if p > cap { (p - cap, cap) } else { (0.0, p) };

    // --- Infiltration (exponential decay with soil saturation) ---
    // SQ = 2 is hardcoded following HOOPLA's modified SIMHYD
    let rinf = x8 * (-2.0 * *s / x2).exp();
    let (srun, filt) = if exc > rinf {
        (exc - rinf, rinf)
    } else {
        (0.0, exc)
    };

    // --- Interflow and groundwater recharge ---
    let saturation = *s / x2;
    let sint = saturation * filt / x6;
    let rec = (saturation * (filt - sint) / x7).max(0.0);

    // --- Update soil moisture ---
    *s += filt - sint - rec;

    // --- Soil moisture excess ---
    let ex2 = if *s > x2 {
        let excess = *s - x2;
        *s = x2;
        excess
    } else {
        0.0
    };

    // --- Actual evapotranspiration from soil ---
    // CAP2 = 10 mm is hardcoded following HOOPLA
    let et = (e - e1).min(10.0 * *s / x2);
    *s = (*s - et).max(0.0);

    // --- Ground reservoir (slow) ---
    *r += ex2 + rec;
    let qr = *r / (x3 * x5);
    *r -= qr;

    // --- Routing reservoir (fast) ---
    *t += sint + srun + qr;
    let qt = *t / x5;
    *t -= qt;

    // --- Delay routing ---
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * qt;
    }
    hy[n - 1] = dl[n - 1] * qt;

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
    let m = PyModule::new(py, "simhyd")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
