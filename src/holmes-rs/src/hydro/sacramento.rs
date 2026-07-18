use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

// Fixed interception and lower-zone routing capacities from Perrin's
// "version retenue" of the Sacramento model (thesis annex, fiche n°27).
const XF1: f64 = 3.0;
const XF2: f64 = 30.0;

pub const param_names: &[&str] =
    &["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9"];

pub const param_descriptions: &[&str] = &[
    "Direct routing reservoir capacity (d)",
    "Upper zone free-water capacity (mm)",
    "Lower zone emptying constant (d)",
    "Upper zone tension-water capacity (mm)",
    "Maximum percolation rate (mm/d)",
    "Hypodermic flow emptying constant (d)",
    "Upper zone partitioning coefficient (-)",
    "Deep percolation coefficient (-)",
    "Delay (d)",
];

// Lower bounds on x1, x3, x6, x8 are strictly >= 1 so that the linear
// outflow q = storage / constant never exceeds the stored volume, which
// keeps every reservoir non-negative by construction.
const BOUNDS: [(&str, f64, f64); 9] = [
    ("x1", 1.0, 20.0),
    ("x2", 30.0, 1000.0),
    ("x3", 10.0, 500.0),
    ("x4", 10.0, 500.0),
    ("x5", 0.01, 20.0),
    ("x6", 1.0, 100.0),
    ("x7", 0.01, 0.99),
    ("x8", 1.0, 50.0),
    ("x9", 0.5, 10.0),
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

    let (mut s, mut t, mut r, mut l, mut m, dl, mut hy) = init_state(x9);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x4, x5, x6, x7, x8, &mut s,
                &mut t, &mut r, &mut l, &mut m, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "SACRAMENTO simulation")?;

    Ok(result)
}

#[allow(clippy::type_complexity)]
fn init_state(x9: f64) -> (f64, f64, f64, f64, f64, Array1<f64>, Array1<f64>) {
    // Initial reservoir states from HOOPLA ini_HydroMod14.m — matches the
    // moderately wet catchment state recommended in Perrin's fiche n°27.
    let s = 3.0;
    let t = 10.0;
    let r = 100.0;
    let l = 0.0;
    let m = 0.0;

    // Fractional-delay routing, same construction as GR4J/GARDENIA:
    // DL[n-2] carries the fractional remainder of x9 and DL[n-1] the
    // complement, so non-integer delays are represented without
    // per-step interpolation.
    let size = x9.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x9 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

    (s, t, r, l, m, dl, hy)
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
    x6: f64,
    x7: f64,
    x8: f64,
    s: &mut f64,
    t: &mut f64,
    r: &mut f64,
    l: &mut f64,
    m: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    let (is_flux, e_residual) = update_surface(p, e, s);
    let production =
        update_production(is_flux, e_residual, x2, x4, x5, x6, t, *r);
    let qr = update_base_flow(
        production.it,
        production.e_deep,
        x2,
        x3,
        x7,
        x8,
        l,
        r,
    );
    let qm = update_direct_routing(production.qt0, x1, m);
    update_hydrograph(qr + qm + production.qt1, dl, hy);
    hy[0].max(0.0)
}

struct Production {
    qt0: f64,
    qt1: f64,
    it: f64,
    e_deep: f64,
}

fn update_surface(p: f64, e: f64, s: &mut f64) -> (f64, f64) {
    // S is the interception reservoir with fixed capacity XF1. Any excess
    // spills into the tension store T. Returns (spilled water, leftover
    // PET that did not evaporate from S).
    *s += p;
    let es = e.min(*s);
    *s -= es;
    let e_residual = e - es;
    let is_flux = (*s - XF1).max(0.0);
    *s -= is_flux;
    (is_flux, e_residual)
}

#[allow(clippy::too_many_arguments)]
fn update_production(
    is_flux: f64,
    e_residual: f64,
    x2: f64,
    x4: f64,
    x5: f64,
    x6: f64,
    t: &mut f64,
    r: f64,
) -> Production {
    // T is the upper-zone tension-water store (uztwm in Burnash notation).
    // Within one step it emits, in order: percolation It to the free-water
    // store (damped by R's filling ratio R/x2), hypodermic flow Qt1 toward
    // the channel, evaporation Et, and saturation overflow Qt0 above x4.
    *t += is_flux;

    // HOOPLA HM14: It = max(0, min(T, x5 * (1 - R/x2) * T/x4)). The clamp
    // also guards against R temporarily exceeding x2 (would make the
    // parenthesized term negative).
    let it = (x5 * (1.0 - r / x2) * (*t / x4)).clamp(0.0, *t);
    *t -= it;

    let qt1 = *t / x6;
    *t -= qt1;

    let et = (e_residual * (1.0_f64).min(*t / x4)).min(*t);
    *t -= et;
    let e_deep = e_residual - et;

    let qt0 = (*t - x4).max(0.0);
    *t -= qt0;

    Production {
        qt0,
        qt1,
        it,
        e_deep,
    }
}

#[allow(clippy::too_many_arguments)]
fn update_base_flow(
    it: f64,
    e_deep: f64,
    x2: f64,
    x3: f64,
    x7: f64,
    x8: f64,
    l: &mut f64,
    r: &mut f64,
) -> f64 {
    // Percolation It is partitioned between the lower-zone routing store L
    // (fraction x7) and the upper-zone free-water store R (fraction 1-x7).
    // L drains fast above its cap XF2, and the overflow Il tops up R.
    *l += x7 * it;
    let il = (*l - XF2).max(0.0);
    *l -= il;
    *r += (1.0 - x7) * it + il;

    // Residual PET from the tension store evaporates L proportionally to
    // its share of the combined interception + routing capacity.
    let el = e_deep * *l / (XF1 + XF2);
    *l -= el;

    // Mass-balance correction: if El drove L below zero, pull the deficit
    // Ir from the free space of R above x2 - XF2. This is the only place
    // water moves "up" in the model.
    if *l < 0.0 {
        let ir = (-*l).min((*r - (x2 - XF2)).max(0.0));
        *l = (*l + ir).max(0.0);
        *r -= ir;
    }

    // R drains linearly toward the outlet; the deep-percolation coefficient
    // x8 damps the outflow (x8 >= 1, so dividing again reduces Qr).
    let qr = *r / x3;
    *r -= qr;
    qr / x8
}

fn update_direct_routing(qt0: f64, x1: f64, m: &mut f64) -> f64 {
    // M is the fast channel-routing store fed only by tension-store
    // overflow. It drains linearly with time constant x1.
    *m += qt0;
    let qm = *m / x1;
    *m -= qm;
    qm
}

fn update_hydrograph(q: f64, dl: &Array1<f64>, hy: &mut Array1<f64>) {
    // Shift-and-add convolution equivalent to HOOPLA's:
    //   HY = [HY(2:end); 0] + DL * (Qr + Qm + Qt1);
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * q;
    }
    hy[n - 1] = dl[n - 1] * q;
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
    let m = PyModule::new(py, "sacramento")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
