use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4", "x5", "x6"];

pub const param_descriptions: &[&str] = &[
    "Rain correction coefficient (-)",
    "Emptying constant of reservoir L (d)",
    "Emptying constant of reservoir N (-)",
    "Response time of unit hydrograph UH2 (d)",
    "Capacity of reservoir U (mm)",
    "Capacity of reservoir L (mm)",
];

pub const param_descriptions_fr: &[&str] = &[
    "Coefficient de correction de la pluie (-)",
    "Constante de vidange du réservoir L (d)",
    "Constante de vidange du réservoir N (-)",
    "Temps de réponse de l'hydrogramme unitaire UH2 (d)",
    "Capacité du réservoir U (mm)",
    "Capacité du réservoir L (mm)",
];

const BOUNDS: [(&str, f64, f64); 6] = [
    ("x1", 0.5, 2.0),
    ("x2", 1.0, 1000.0),
    ("x3", 0.01, 100.0),
    ("x4", 0.5, 10.0),
    ("x5", 1.0, 1000.0),
    ("x6", 1.0, 1000.0),
];

/// Fixed maximum capacity of the deep soil reservoir Z (mm).
const Z_MAX: f64 = 90.0;

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

    // Initialize reservoir states
    let mut u: f64 = x5 * 0.5;
    let mut l: f64 = x6 * 0.5;
    let mut z: f64 = 50.0;
    let mut n: f64 = 0.5;

    // Create UH2 weights and three convolution state vectors
    let uh2 = create_uh2(x4);
    let uh_len = uh2.len();
    let mut h2_vsal = vec![0.0; uh_len];
    let mut h2_rur = vec![0.0; uh_len];
    let mut h2_vn = vec![0.0; uh_len];

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|t, &p, &e| {
            streamflow[t] = run_step(
                p,
                e,
                x1,
                x2,
                x3,
                x5,
                x6,
                &mut u,
                &mut l,
                &mut z,
                &mut n,
                &uh2,
                &mut h2_vsal,
                &mut h2_rur,
                &mut h2_vn,
            );
        });

    let result = Array1::from_vec(streamflow);
    validate_output(result.view(), "MORDOR simulation")?;
    Ok(result)
}

/// Create UH2 unit hydrograph weights (double-sided, exponent 2.5).
///
/// S-curve:
///   SH2(t) = 0.5 * (t/x4)^2.5           for 0 <= t <= x4
///   SH2(t) = 1 - 0.5 * (2 - t/x4)^2.5   for x4 < t <= 2*x4
///   SH2(t) = 1                            for t > 2*x4
///
/// UH2 weights = diff(SH2).
fn create_uh2(x4: f64) -> Vec<f64> {
    let sh2 = |t: f64| -> f64 {
        if t <= 0.0 {
            0.0
        } else if t <= x4 {
            0.5 * (t / x4).powf(2.5)
        } else if t <= 2.0 * x4 {
            1.0 - 0.5 * (2.0 - t / x4).powf(2.5)
        } else {
            1.0
        }
    };

    let n = (2.0 * x4).ceil() as usize;
    (1..=n)
        .map(|i| sh2(i as f64) - sh2(i as f64 - 1.0))
        .collect()
}

/// Route a flow component through a UH2 convolution state vector.
fn route_through_uh2(flow: f64, state: &mut [f64], uh2: &[f64]) {
    let n = state.len();
    for i in 0..n.saturating_sub(1) {
        state[i] = state[i + 1] + uh2[i] * flow;
    }
    if n > 0 {
        state[n - 1] = uh2[n - 1] * flow;
    }
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
    u: &mut f64,
    l: &mut f64,
    z: &mut f64,
    n: &mut f64,
    uh2: &[f64],
    h2_vsal: &mut [f64],
    h2_rur: &mut [f64],
    h2_vn: &mut [f64],
) -> f64 {
    // =====================================================================
    // Production phase
    // =====================================================================

    // Corrected precipitation
    let pl = p * x1;

    // Rainfall partitioning proportional to U filling ratio
    let dtr1 = pl * (*u / x5);
    let dtu1 = pl - dtr1;

    // Surface runoff = direct runoff + overflow from U
    let vs = dtr1 + (*u + dtu1 - x5).max(0.0);

    // Update U reservoir (capped at x5)
    *u = (*u + dtu1).min(x5);

    // Evapotranspiration from U — limited by U level, capacity, and
    // PET-weighted filling ratio
    let evu = (*u).min(x5).min((e * *u / x5).max(0.0));
    *u -= evu;

    // Infiltration to L reservoir — limited by available capacity
    let al = (x6 - *l).max(0.0).min(vs * (1.0 - *l / x6).max(0.0));
    *l += al;

    // Linear drainage from L
    let vl = *l / x2;
    *l -= vl;

    // Percolation from L drainage to Z, plus underground runoff components
    let z_ratio = *z / Z_MAX;
    let dtz = vl * (1.0 - z_ratio);
    let rur = 0.2 * vl * z_ratio; // rapid underground runoff
    let an = 0.8 * vl * z_ratio; // slow underground recharge

    // Update Z reservoir
    *z += dtz;
    let remaining_pet = (e - evu).max(0.0);
    let evz = (*z).min(remaining_pet * *z / Z_MAX);
    *z = (*z - evz).clamp(0.0, Z_MAX);

    // Update N reservoir (groundwater)
    *n += an;
    let vn = (*n).min((*n / x3).powi(3));
    *n = (*n - vn).max(0.0);

    // =====================================================================
    // Routing phase — three components through UH2
    // =====================================================================

    let flow_vsal = (vs - al).max(0.0);
    route_through_uh2(flow_vsal, h2_vsal, uh2);
    route_through_uh2(rur, h2_rur, uh2);
    route_through_uh2(vn, h2_vn, uh2);

    // Total streamflow = sum of routed components (non-negative).
    // UH2 always has ≥1 element (x4 ≥ 0.5 → ceil(2·x4) ≥ 1), so
    // first() always succeeds; unwrap_or is a safety net.
    h2_vsal.first().copied().unwrap_or(0.0).max(0.0)
        + h2_rur.first().copied().unwrap_or(0.0).max(0.0)
        + h2_vn.first().copied().unwrap_or(0.0).max(0.0)
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
    let m = PyModule::new(py, "mordor")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add("param_descriptions_fr", param_descriptions_fr)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
