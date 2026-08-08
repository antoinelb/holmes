use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4", "x5", "x6"];

pub const param_descriptions: &[&str] = &[
    "Maximum capacity of soil reservoir (mm)",
    "Spatial variability of soil moisture capacity (-)",
    "Distribution factor of fast/slow flows (-)",
    "Delay (d)",
    "Emptying constant of slow routing reservoir (-)",
    "Emptying constant of fast routing reservoir (d)",
];

pub const param_descriptions_fr: &[&str] = &[
    "Capacité maximale du réservoir de sol (mm)",
    "Variabilité spatiale de la capacité en eau du sol (-)",
    "Facteur de répartition des écoulements rapides/lents (-)",
    "Délai (d)",
    "Constante de vidange du réservoir de routage lent (-)",
    "Constante de vidange du réservoir de routage rapide (d)",
];

const BOUNDS: [(&str, f64, f64); 6] = [
    ("x1", 1.0, 1500.0),
    ("x2", 0.1, 2.0),
    ("x3", 0.01, 0.99),
    ("x4", 0.1, 5.0),
    ("x5", 1.0, 1000.0),
    ("x6", 1.0, 10.0),
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

    let (mut s, mut r1, mut r2, mut r3, mut t, dl, mut hy) =
        init_state(x1, x2, x4);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x5, x6, &mut s, &mut r1, &mut r2,
                &mut r3, &mut t, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "HYMOD simulation")?;

    Ok(result)
}

fn init_state(
    x1: f64,
    x2: f64,
    x4: f64,
) -> (f64, f64, f64, f64, f64, Array1<f64>, Array1<f64>) {
    // HOOPLA initializes S at 20 % of Cmax, but the Pareto update requires
    // S <= x1 / (x2 + 1). Clamp so the first step's power-base stays >= 0.
    let s = (x1 * 0.2).min(x1 / (x2 + 1.0));
    let r1 = 1.0;
    let r2 = 1.0;
    let r3 = 1.0;
    let t = 300.0;

    let size = x4.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x4 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

    (s, r1, r2, r3, t, dl, hy)
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
    r1: &mut f64,
    r2: &mut f64,
    r3: &mut f64,
    t: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    let xs = *s;

    // "Current" saturation capacity matching the current soil water (Pareto)
    let base = (1.0 - (x2 + 1.0) * *s / x1).max(0.0);
    let ctprev = x1 * (1.0 - base.powf(1.0 / (x2 + 1.0)));

    // Saturation excess (runoff from already-saturated fraction)
    let ut1 = (p - x1 + ctprev).max(0.0);

    // Net rain reaching the soil
    let pn = p - ut1;

    // Update soil water via inverse Pareto
    let dum = ((ctprev + pn) / x1).min(1.0);
    *s = x1 / (x2 + 1.0) * (1.0 - (1.0 - dum).powf(x2 + 1.0));

    // Excess = net rain minus storage increase
    let ut2 = (pn - (*s - xs)).max(0.0);

    // Evapotranspiration at demand
    *s = (*s - e).max(0.0);

    // Flow splitting: fast path takes saturation excess + alpha-fraction of Ut2
    let uq = x3 * ut2 + ut1;
    let us = (1.0 - x3) * ut2;

    // Slow (ground) reservoir: residence time x5 * x6
    *t += us;
    let qt = *t / (x5 * x6);
    *t -= qt;

    // Three fast reservoirs in cascade, each with residence time x6
    *r1 += uq;
    let q1 = *r1 / x6;
    *r1 -= q1;

    *r2 += q1;
    let q2 = *r2 / x6;
    *r2 -= q2;

    *r3 += q2;
    let q3 = *r3 / x6;
    *r3 -= q3;

    // Delay / unit-hydrograph convolution
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * (qt + q3);
    }
    hy[n - 1] = dl[n - 1] * (qt + q3);

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
    let m = PyModule::new(py, "hymod")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add("param_descriptions_fr", param_descriptions_fr)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
