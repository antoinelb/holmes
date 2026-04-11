use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] =
    &["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"];

pub const param_descriptions: &[&str] = &[
    "Soil reservoir capacity (mm)",
    "PET threshold (mm)",
    "Upper emptying constant of intermediate reservoir (d)",
    "Ground reservoir emptying constant (d)",
    "Percolation coefficient (mm/d)",
    "Triangular unit hydrograph time base (d)",
    "Soil nonlinearity exponent (-)",
    "Flow threshold of intermediate reservoir (mm)",
    "Lower emptying constant of intermediate reservoir (-)",
];

// Lower bounds on x2 and x9 are tightened relative to HOOPLA (which allows 0)
// to avoid division by zero and guarantee x3 * x9 >= 1, which keeps the
// intermediate reservoir R non-negative by construction.
const BOUNDS: [(&str, f64, f64); 9] = [
    ("x1", 100.0, 1000.0),
    ("x2", 1.0, 1000.0),
    ("x3", 1.0, 20.0),
    ("x4", 1.0, 100.0),
    ("x5", 1.0, 20.0),
    ("x6", 2.0, 40.0),
    ("x7", 0.0, 50.0),
    ("x8", 0.0, 100.0),
    ("x9", 1.0, 20.0),
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
        [BOUNDS[8].1, BOUNDS[8].2],
    ];
    let default_values = bounds.sum_axis(Axis(1)) / 2.0;
    (default_values, bounds)
}

pub fn simulate(
    params: ArrayView1<f64>,
    precipitation: ArrayView1<f64>,
    pet: ArrayView1<f64>,
) -> Result<Array1<f64>, HydroError> {
    let [x1, x2, x3, x4, x5, x6, x7, x8, x9]: [f64; 9] = params
        .as_slice()
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| HydroError::ParamsMismatch(9, params.len()))?;

    for (i, &param_value) in
        [x1, x2, x3, x4, x5, x6, x7, x8, x9].iter().enumerate()
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

    let (mut s, mut r, mut t, unit_hydrograph, mut hydrograph) =
        init_state(x1, x6);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t,
                pet_t,
                x1,
                x2,
                x3,
                x4,
                x5,
                x7,
                x8,
                x9,
                &mut s,
                &mut r,
                &mut t,
                &unit_hydrograph,
                &mut hydrograph,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "HBV simulation")?;

    Ok(result)
}

fn init_state(x1: f64, x6: f64) -> (f64, f64, f64, Vec<f64>, Vec<f64>) {
    // Reservoir initial states from HOOPLA ini_HydroMod6.m:
    //   soil reservoir at capacity, intermediate and ground reservoirs seeded small
    let s = x1;
    let r = 1.0;
    let t = 10.0;

    let unit_hydrograph = build_unit_hydrograph(x6);
    let hydrograph = vec![0.0; unit_hydrograph.len()];

    (s, r, t, unit_hydrograph, hydrograph)
}

fn build_unit_hydrograph(x6: f64) -> Vec<f64> {
    // Triangular unit hydrograph of time base x6 (>= 2 enforced by BOUNDS).
    // Rising limb indices 1..=floor(x6/2) with weight k-0.5; recession limb
    // indices floor(x6/2)+1..=ceil(x6) with weight x6+0.5-k; normalized.
    let half = (x6 / 2.0).floor() as usize;
    let full = x6.ceil() as usize;
    let mut uh: Vec<f64> = Vec::with_capacity(full.max(1));
    for k in 1..=half {
        uh.push(k as f64 - 0.5);
    }
    for k in (half + 1)..=full {
        uh.push(x6 + 0.5 - k as f64);
    }
    let total: f64 = uh.iter().sum();
    for w in uh.iter_mut() {
        *w /= total;
    }
    uh
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
    x8: f64,
    x9: f64,
    s: &mut f64,
    r: &mut f64,
    t: &mut f64,
    unit_hydrograph: &[f64],
    hydrograph: &mut [f64],
) -> f64 {
    let pr = update_soil(p, e, x1, x2, x7, s);
    let q = update_routing(pr, x3, x4, x5, x8, x9, r, t);
    update_hydrograph(q, unit_hydrograph, hydrograph);
    hydrograph[0].max(0.0)
}

fn update_soil(p: f64, e: f64, x1: f64, x2: f64, x7: f64, s: &mut f64) -> f64 {
    // Five sub-step splitting of the soil moisture accounting, per HOOPLA HM6.
    // At each sub-step: a fraction (S/x1)^x7 of P5 overflows into routing (Pr),
    // the remainder refills the soil, then PET reduced by S/x2 drains it.
    let p5 = p / 5.0;
    let e5 = e / 5.0;
    let mut pr = 0.0;
    for _ in 0..5 {
        let fill_ratio = (*s / x1).min(1.0);
        let pri = p5 * fill_ratio.powf(x7);
        pr += pri;
        *s += p5 - pri;
        let esi = (e5 * *s / x2).min(*s);
        *s -= esi;
    }
    pr
}

#[allow(clippy::too_many_arguments)]
fn update_routing(
    pr: f64,
    x3: f64,
    x4: f64,
    x5: f64,
    x8: f64,
    x9: f64,
    r: &mut f64,
    t: &mut f64,
) -> f64 {
    // Intermediate reservoir R emits two components: a threshold-linear upper
    // outflow Qr1 above x8 and a linear lower outflow Qr2. Whatever remains
    // percolates (capped at x5) into the ground reservoir T which drains
    // linearly as Qt. Bounds guarantee x3 * x9 >= 1 so R stays non-negative.
    *r += pr;

    let qr1 = ((*r - x8) / x3).max(0.0);
    *r -= qr1;

    let qr2 = *r / (x3 * x9);
    *r -= qr2;

    let ir = (*r).min(x5);
    *r -= ir;

    *t += ir;
    let qt = *t / x4;
    *t -= qt;

    qr1 + qr2 + qt
}

fn update_hydrograph(q: f64, unit_hydrograph: &[f64], hydrograph: &mut [f64]) {
    // Shift-and-add convolution equivalent to HOOPLA:
    //   H = [H(2:end); 0] + UH * Q;
    let n = hydrograph.len();
    for i in 0..n - 1 {
        hydrograph[i] = hydrograph[i + 1] + q * unit_hydrograph[i];
    }
    hydrograph[n - 1] = q * unit_hydrograph[n - 1];
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
    let m = PyModule::new(py, "hbv")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
