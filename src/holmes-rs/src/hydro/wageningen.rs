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
    "Percolation emptying threshold (mm)",
    "Maximum soil reservoir capacity (mm)",
    "Infiltration emptying constant (mm)",
    "Capillary rise parameter (d)",
    "Flow dissociation parameter (mm)",
    "Fast routing emptying constant (d)",
    "Slow routing emptying multiplier (-)",
    "Delay (d)",
];

pub const param_descriptions_fr: &[&str] = &[
    "Seuil de vidange par percolation (mm)",
    "Capacité maximale du réservoir de sol (mm)",
    "Constante de vidange par infiltration (mm)",
    "Paramètre de remontée capillaire (d)",
    "Paramètre de dissociation des écoulements (mm)",
    "Constante de vidange du routage rapide (d)",
    "Multiplicateur de vidange du routage lent (-)",
    "Délai (d)",
];

const BOUNDS: [(&str, f64, f64); 8] = [
    ("x1", 1.0, 500.0),
    ("x2", 10.0, 2000.0),
    ("x3", 0.1, 1000.0),
    ("x4", 1.0, 1000.0),
    ("x5", 0.1, 500.0),
    ("x6", 0.5, 50.0),
    ("x7", 1.0, 50.0),
    ("x8", 0.5, 5.0),
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

    let (mut s, mut r, mut t, dl, mut hy) = init_state(x8);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x4, x5, x6, x7, &mut s, &mut r,
                &mut t, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);
    validate_output(result.view(), "WAGENINGEN simulation")?;
    Ok(result)
}

fn init_state(x8: f64) -> (f64, f64, f64, Array1<f64>, Array1<f64>) {
    // Warm-start reservoir states from HOOPLA ini_HydroMod19.m
    let s = 30.0;
    let r = 0.0;
    let t = 200.0;

    let size = x8.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x8 - size as f64 + 3.0);
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
    x4: f64,
    x5: f64,
    x6: f64,
    x7: f64,
    s: &mut f64,
    r: &mut f64,
    t: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // Production: soil reservoir S receives precipitation
    *s += p;

    // Percolation Is and capillary rise It are mutually exclusive:
    // above threshold x1, water leaves S toward routing; below, T rises into S.
    let (is_flux, it_flux) = if *s >= x1 {
        ((*s / x2) * ((*s - x1) / x3), 0.0)
    } else {
        (0.0, (*t / x4) * (x1 - *s))
    };

    *s = *s + it_flux - is_flux;

    // Actual evapotranspiration: full PET above threshold, cosine-reduced below
    let e_s = if *s >= x1 {
        e
    } else {
        e * ((std::f64::consts::PI / 2.0) * ((x1 - *s) / x1)).cos()
    };

    *s = (*s - e_s).max(0.0);

    // Flow dissociation: slow reservoir T takes (1-DIV), fast reservoir R takes DIV
    let div = (*t / x5).min(1.0);
    *t += (1.0 - div) * is_flux;
    *r += div * is_flux;

    // Routing: fast reservoir R empties linearly with time constant x6
    let q_r = *r / x6;
    *r -= q_r;

    // Slow reservoir T empties with time constant x6 * x7 (x7 > 1 ⇒ slower)
    let q_t = *t / (x6 * x7);
    *t -= q_t;

    // Delay hydrograph
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * (q_r + q_t);
    }
    hy[n - 1] = dl[n - 1] * (q_r + q_t);

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
    let m = PyModule::new(py, "wageningen")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add("param_descriptions_fr", param_descriptions_fr)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
