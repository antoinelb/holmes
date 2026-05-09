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
    "Maximum capacity of production reservoir (mm)",
    "Spatial variability of soil moisture capacity (-)",
    "Drainage threshold as a fraction of maximum storage (-)",
    "Routing delay (d)",
    "Cubic ground reservoir characteristic storage (mm)",
    "Linear routing reservoirs emptying constant (d)",
    "Rainfall correction factor (-)",
    "Drainage time constant (d)",
];

// Lower bounds on x6 and x8 are >= 1 so that the linear outflows
// q = storage / constant never exceed the stored volume, keeping
// every reservoir non-negative by construction.
const BOUNDS: [(&str, f64, f64); 8] = [
    ("x1", 10.0, 2000.0),
    ("x2", 0.01, 2.0),
    ("x3", 0.01, 0.99),
    ("x4", 0.5, 5.0),
    ("x5", 1.0, 2000.0),
    ("x6", 1.0, 30.0),
    ("x7", 0.5, 1.5),
    ("x8", 1.0, 100.0),
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

    let (mut s, mut t, mut m, mut n, dl, mut hy) = init_state(x1, x2, x4);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x5, x6, x7, x8, &mut s, &mut t,
                &mut m, &mut n, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "PDM simulation")?;

    Ok(result)
}

#[allow(clippy::type_complexity)]
fn init_state(
    x1: f64,
    x2: f64,
    x4: f64,
) -> (f64, f64, f64, f64, Array1<f64>, Array1<f64>) {
    // HOOPLA initializes S at 20 % of Cmax, but the Pareto inverse
    // update requires S <= x1 / (x2 + 1) for the power base to stay
    // non-negative. Clamp defensively even though the current bounds
    // already keep 0.2 * Cmax safely below the limit.
    let s = (x1 * 0.2).min(x1 / (x2 + 1.0));
    let t = 20.0;
    let m = 30.0;
    let n = 30.0;

    // Fractional-delay routing identical to GARDENIA / HYMOD: the
    // unit pulse is split between the two final entries of the buffer
    // so that non-integer delays do not need per-step interpolation.
    let size = x4.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x4 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

    (s, t, m, n, dl, hy)
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
    t: &mut f64,
    m: &mut f64,
    n: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // --- Production phase (Pareto-distributed soil store) ---
    let p1 = p * x7;
    let xs = *s;

    // Inverse Pareto: equivalent uniform depth currently filled.
    let base = (1.0 - (x2 + 1.0) * *s / x1).max(0.0);
    let ctprev = x1 * (1.0 - base.powf(1.0 / (x2 + 1.0)));

    // Saturation excess: rain that lands on already-full cells.
    let ut1 = (p1 - x1 + ctprev).max(0.0);
    let pn = p1 - ut1;

    // Forward Pareto: update the soil water given the net rain.
    let dum = ((ctprev + pn) / x1).min(1.0);
    *s = x1 / (x2 + 1.0) * (1.0 - (1.0 - dum).powf(x2 + 1.0));

    // Infiltration excess: net rain that did not fit into the store.
    let ut2 = (pn - (*s - xs)).max(0.0);

    // Evaporation, scaled by the current soil filling fraction.
    let fill = (*s / x1) * (x2 + 1.0);
    let evap_factor = 1.0 - (1.0 - fill).powi(2);
    *s = (*s - e * evap_factor).max(0.0);

    // Threshold drainage: only when S exceeds Alpha-fraction of S_max.
    let threshold = x1 / (x2 + 1.0) * x3;
    let drg = if *s > threshold {
        (*s - threshold) / x8
    } else {
        0.0
    };
    *s -= drg;

    // --- Routing ---
    // Fast pathway: two linear reservoirs in series fed by surface runoff.
    let uq = ut1 + ut2;
    *m += uq;
    let q1 = *m / x6;
    *m -= q1;

    *n += q1;
    let q2 = *n / x6;
    *n -= q2;

    // Slow pathway: cubic ground reservoir fed by subsurface drainage.
    *t += drg;
    let qt = *t * (1.0 - (1.0 + (*t / x5).powi(2)).powf(-0.5));
    *t -= qt;

    // --- Convolution with the fractional unit hydrograph ---
    let n_hy = hy.len();
    for i in 0..n_hy - 1 {
        hy[i] = hy[i + 1] + dl[i] * (qt + q2);
    }
    hy[n_hy - 1] = dl[n_hy - 1] * (qt + q2);

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
    let simulation =
        simulate(params.as_array(), precipitation.as_array(), pet.as_array())?;
    Ok(simulation.to_pyarray(py))
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "pdm")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
