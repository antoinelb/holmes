use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &[
    "x1", // infiltration threshold (mm)
    "x2", // soil reservoir drainage threshold (mm)
    "x3", // infiltration constant (-)
    "x4", // upper lateral drainage constant (-)
    "x5", // max soil reservoir capacity (mm)
    "x6", // delay (days)
    "x7", // groundwater drainage threshold (mm)
    "x8", // lower lateral drainage constant (-)
    "x9", // lower groundwater drainage constant (-)
];

const BOUNDS: [(&str, f64, f64); 9] = [
    ("x1", 0.0, 3000.0),
    ("x2", 1.0, 3000.0),
    ("x3", 1.0, 100.0),
    ("x4", 1.0, 50.0),
    ("x5", 1.0, 8000.0),
    ("x6", 0.1, 20.0),
    ("x7", 0.01, 500.0),
    ("x8", 1.0, 1000.0),
    ("x9", 1.0, 3000.0),
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
        [BOUNDS[8].1, BOUNDS[8].2]
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

    let (mut surface_store, mut groundwater_store, dl, mut hy) =
        init_state(x5, x6);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|t, &precip_t, &pet_t| {
            streamflow[t] = run_step(
                &mut surface_store,
                &mut groundwater_store,
                &mut hy,
                &dl,
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
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "CEQUEAU simulation")?;

    Ok(result)
}

fn init_state(x5: f64, x6: f64) -> (f64, f64, Array1<f64>, Array1<f64>) {
    let surface_store = 500.0;
    let groundwater_store = x5 * 0.2;

    let size = x6.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x6 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

    (surface_store, groundwater_store, dl, hy)
}

#[allow(clippy::too_many_arguments)]
fn run_step(
    surface_store: &mut f64,
    groundwater_store: &mut f64,
    hy: &mut Array1<f64>,
    dl: &Array1<f64>,
    precipitation: f64,
    pet: f64,
    x1: f64,
    x2: f64,
    x3: f64,
    x4: f64,
    x5: f64,
    x7: f64,
    x8: f64,
    x9: f64,
) -> f64 {
    // net inputs
    *surface_store += precipitation;
    let surface_pet =
        (pet * (2.0 * *surface_store / x5).min(1.0)).min(*surface_store);
    *surface_store -= surface_pet;
    let remaining_pet = pet - surface_pet;

    // percolation
    let percolation = (*surface_store - x1).max(0.0) / x3;
    *surface_store -= percolation;

    // surface routing
    let surface_streamflow_2 = (*surface_store - x2).max(0.0) / x4;
    *surface_store -= surface_streamflow_2;
    let surface_streamflow_3 = *surface_store / (x4 * x8);
    *surface_store -= surface_streamflow_3;
    let surface_streamflow_1 = (*surface_store - x5).max(0.0);
    *surface_store -= surface_streamflow_1;

    // groundwater routing
    *groundwater_store += percolation;
    let groundwater_streamflow_1 =
        (*groundwater_store - x7).max(0.0) / (x4 * x9);
    *groundwater_store -= groundwater_streamflow_1;
    let groundwater_streamflow_2 = *groundwater_store / (x4 * x8 * x9 * x9);
    *groundwater_store -= groundwater_streamflow_2;
    let groundwater_pet = ((*groundwater_store / x7).min(1.0) * remaining_pet)
        .min(*groundwater_store);
    *groundwater_store -= groundwater_pet;

    // total streamflow
    let total_streamflow = surface_streamflow_1
        + surface_streamflow_2
        + surface_streamflow_3
        + groundwater_streamflow_1
        + groundwater_streamflow_2;
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * total_streamflow;
    }
    hy[n - 1] = dl[n - 1] * total_streamflow;

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
    let m = PyModule::new(py, "cequeau")?;
    m.add("param_names", param_names)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
