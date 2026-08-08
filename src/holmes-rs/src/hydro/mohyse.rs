use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4", "x5", "x6", "x7"];

pub const param_descriptions: &[&str] = &[
    "Transpiration coefficient (-)",
    "Maximum infiltration capacity (mm)",
    "Emptying coefficient of aquifer vadose zone (-)",
    "Emptying coefficient of river vadose zone (-)",
    "Aquifer to river emptying coefficient (-)",
    "Unit hydrograph shape parameter (-)",
    "Unit hydrograph scale parameter (-)",
];

pub const param_descriptions_fr: &[&str] = &[
    "Coefficient de transpiration (-)",
    "Capacité maximale d'infiltration (mm)",
    "Coefficient de vidange de la zone vadose vers l'aquifère (-)",
    "Coefficient de vidange de la zone vadose vers la rivière (-)",
    "Coefficient de vidange de l'aquifère vers la rivière (-)",
    "Paramètre de forme de l'hydrogramme unitaire (-)",
    "Paramètre d'échelle de l'hydrogramme unitaire (-)",
];

const BOUNDS: [(&str, f64, f64); 7] = [
    ("x1", 0.01, 1.0),
    ("x2", 1.0, 2000.0),
    ("x3", 0.001, 1.0),
    ("x4", 0.001, 1.0),
    ("x5", 0.001, 1.0),
    ("x6", 1.0, 5.0),
    ("x7", 0.5, 5.0),
];

/// Fixed unit hydrograph memory length, matching HOOPLA HM10.
const UH_LENGTH: usize = 80;

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

    // Pre-compute gamma-shaped unit hydrograph from x6 (alpha) and x7 (beta)
    let uh = compute_unit_hydrograph(x6, x7);
    let uh_len = uh.len();

    // Initial reservoir states (HOOPLA HM10 defaults)
    let mut s: f64 = 40.0;
    let mut r: f64 = 30.0;
    let mut hy = vec![0.0; uh_len];

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|t, &p, &e| {
            streamflow[t] = run_step(
                p, e, x1, x2, x3, x4, x5, &mut s, &mut r, &uh, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);
    validate_output(result.view(), "MOHYSE simulation")?;
    Ok(result)
}

/// Build a normalised gamma-shaped unit hydrograph.
///
/// UH(t) = t^(alpha-1) · exp(-t/beta) / Σ, for t = 1, 2, …, k.
fn compute_unit_hydrograph(alpha: f64, beta: f64) -> Vec<f64> {
    let mut uh = Vec::with_capacity(UH_LENGTH);
    let mut sum = 0.0;

    for i in 1..=UH_LENGTH {
        let t = i as f64;
        let val = t.powf(alpha - 1.0) * (-t / beta).exp();
        uh.push(val);
        sum += val;
    }

    if sum > 0.0 {
        for val in &mut uh {
            *val /= sum;
        }
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
    s: &mut f64,
    r: &mut f64,
    uh: &[f64],
    hy: &mut [f64],
) -> f64 {
    // Direct evaporation (interception)
    let ed = p.min(e);

    // Transpiration from soil moisture
    let tr = (x1 * *s).min(e - ed);

    // Infiltration (capacity-limited by x2)
    let infiltration = if *s < x2 {
        (p - ed) * (1.0 - *s / x2)
    } else {
        0.0
    };

    // Surface runoff = net rainfall minus infiltration
    let q1 = p - ed - infiltration;

    // Soil drainage to river
    let q2 = x4 * *s;

    // Vadose zone transfer from soil to groundwater
    let qt = x3 * *s;

    // Groundwater flow to river
    let q3 = x5 * *r;

    // Update reservoir states
    *s = (*s + infiltration - tr - qt - q2).max(0.0);
    *r = (*r + qt - q3).max(0.0);

    // Total flow routed through gamma unit hydrograph
    let q_total = q1 + q2 + q3;

    // Shift-and-add convolution
    let n = hy.len();
    for j in 0..n - 1 {
        hy[j] = hy[j + 1] + uh[j] * q_total;
    }
    hy[n - 1] = uh[n - 1] * q_total;

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
    let m = PyModule::new(py, "mohyse")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add("param_descriptions_fr", param_descriptions_fr)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
