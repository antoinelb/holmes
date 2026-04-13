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
    "Direct flow coefficient (-)",
    "Infiltration parameter (-)",
    "PET reduction coefficient for soil layers (-)",
    "Quadratic routing reservoir capacity (mm)",
    "Linear routing reservoir emptying constant (d)",
    "Delay (d)",
    "PET correction coefficient (-)",
    "Flow partitioning coefficient (-)",
];

const BOUNDS: [(&str, f64, f64); 8] = [
    ("x1", 0.01, 1.0),
    ("x2", 0.01, 10.0),
    ("x3", 0.01, 0.99),
    ("x4", 1.0, 500.0),
    ("x5", 1.0, 200.0),
    ("x6", 0.5, 5.0),
    ("x7", 0.1, 2.0),
    ("x8", 0.01, 0.99),
];

// Fixed model constants (from Perrin's thesis, SMAR retained version)
const LAYER_HEIGHT: f64 = 25.0; // mm per soil layer
const NUM_LAYERS: usize = 16; // total soil layers (Z = 400 mm)
const MAX_INFILTRATION: f64 = 200.0; // Ym (mm/d) max infiltration rate
const TOP_CAPACITY: f64 = 125.0; // capacity of top 5 layers (5 × 25 mm)
const TOP_LAYERS: usize = 5; // layers used for moisture sum S

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

    let (mut layers, mut soil_moisture, mut lin, mut quad, dl, mut hy) =
        init_state(x6);

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
                &mut layers,
                &mut soil_moisture,
                &mut lin,
                &mut quad,
                &dl,
                &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);
    validate_output(result.view(), "SMAR simulation")?;
    Ok(result)
}

fn init_state(
    x6: f64,
) -> ([f64; NUM_LAYERS], f64, f64, f64, Array1<f64>, Array1<f64>) {
    let layers = [2.0; NUM_LAYERS];
    let soil_moisture = 100.0; // warm-start S for first step
    let lin = 50.0; // linear routing reservoir L
    let quad = 20.0; // quadratic routing reservoir T

    // delay vector (same construction as HOOPLA / GARDENIA)
    let size = x6.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x6 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];
    let hy = Array1::zeros(size);

    (layers, soil_moisture, lin, quad, dl, hy)
}

#[allow(clippy::too_many_arguments)]
fn run_step(
    p: f64,
    e: f64,
    x1: f64, // direct flow coefficient (H)
    x2: f64, // infiltration parameter (Yc)
    x3: f64, // PET reduction coefficient (C)
    x4: f64, // quadratic routing reservoir capacity
    x5: f64, // linear routing reservoir emptying constant
    x7: f64, // PET correction coefficient (T)
    x8: f64, // partitioning coefficient (G)
    layers: &mut [f64; NUM_LAYERS],
    s: &mut f64,
    l: &mut f64,
    t: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // PET correction
    let e_corr = x7 * e;

    // net inputs
    let pn = (p - e_corr).max(0.0);
    let mut en = (e_corr - p).max(0.0);

    // direct runoff (moisture-dependent fraction of net precipitation)
    let h_prime = x1 * (*s / TOP_CAPACITY);
    let pr1 = h_prime * pn;

    // infiltration capacity (exponential decrease with soil saturation)
    let fr = MAX_INFILTRATION * (-x2 * *s / TOP_CAPACITY).exp();

    // actual infiltration and surface excess
    let mut ps = fr.min((pn - pr1).max(0.0));
    let pr2 = (pn - pr1 - ps).max(0.0);

    // 16-layer soil moisture accounting
    for (i, layer) in layers.iter_mut().enumerate() {
        *layer += ps;
        ps = (*layer - LAYER_HEIGHT).max(0.0);
        *layer -= ps;

        // ET decreases exponentially with depth: C^(i+1)
        let e_layer = (*layer).min(x3.powi((i as i32) + 1) * en);
        *layer -= e_layer;
        en -= e_layer;
    }

    // interflow = drainage from bottom soil layer
    let interflow = ps;

    // recompute soil moisture from top 5 layers
    *s = layers[..TOP_LAYERS].iter().sum();

    // linear routing reservoir (receives (1−G) of interflow)
    *l += (1.0 - x8) * interflow;
    let ql = *l / x5;
    *l -= ql;

    // quadratic routing reservoir (receives G·interflow + surface excess)
    *t += x8 * interflow + pr2;
    let qt = *t * *t / (*t + x4);
    *t -= qt;

    // delay mechanism
    let total_flow = ql + qt + pr1;
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * total_flow;
    }
    hy[n - 1] = dl[n - 1] * total_flow;

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
    let m = PyModule::new(py, "smar")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
