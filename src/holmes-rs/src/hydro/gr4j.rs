use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4"];

const BOUNDS: [(&str, f64, f64); 4] = [
    ("x1", 10.0, 1500.0),
    ("x2", -5.0, 3.0),
    ("x3", 10.0, 400.0),
    ("x4", 0.8, 10.0),
];

pub fn init() -> (Array1<f64>, Array2<f64>) {
    // corresponds to x1, x2, x3, x4
    let bounds = array![
        [BOUNDS[0].1, BOUNDS[0].2],
        [BOUNDS[1].1, BOUNDS[1].2],
        [BOUNDS[2].1, BOUNDS[2].2],
        [BOUNDS[3].1, BOUNDS[3].2]
    ];
    let default_values = bounds.sum_axis(Axis(1)) / 2.0;
    (default_values, bounds)
}

pub fn simulate(
    params: ArrayView1<f64>,
    precipitation: ArrayView1<f64>,
    pet: ArrayView1<f64>,
) -> Result<Array1<f64>, HydroError> {
    let [x1, x2, x3, x4]: [f64; 4] = params
        .as_slice()
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| HydroError::ParamsMismatch(4, params.len()))?;

    for (i, &param_value) in [x1, x2, x3, x4].iter().enumerate() {
        let (name, lower, upper) = BOUNDS[i];
        validate_parameter(param_value, name, lower, upper)?;
    }

    check_lengths(precipitation, pet)?;
    validate_inputs_finite(precipitation, "precipitation")?;
    validate_inputs_finite(pet, "pet")?;
    validate_non_negative(precipitation, "precipitation")?;
    validate_non_negative(pet, "pet")?;

    let mut streamflow: Vec<f64> = vec![0.0; precipitation.len()];

    let mut production_store = x1 / 2.;
    let mut routing_store = x3 / 2.;
    let mut routing_precipitation: f64 = 0.0;
    let mut streamflow_: f64 = 0.0;

    let unit_hydrographs = create_unit_hydrographs(x4);
    let mut hydrographs = (
        vec![0.0; unit_hydrographs.0.len()],
        vec![0.0; unit_hydrographs.1.len()],
    );

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|t, &precip_t, &pet_t| {
            update_production(
                &mut production_store,
                &mut routing_precipitation,
                precip_t,
                pet_t,
                x1,
            );
            update_routing(
                &mut routing_store,
                &mut hydrographs,
                &mut streamflow_,
                &unit_hydrographs,
                routing_precipitation,
                x2,
                x3,
            );
            streamflow[t] = streamflow_;
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "GR4J simulation")?;

    Ok(result)
}

fn create_unit_hydrographs(x4: f64) -> (Vec<f64>, Vec<f64>) {
    let s1 = |i: f64| -> f64 {
        if i == 0. {
            0.
        } else if i >= x4 {
            1.
        } else {
            (i / x4).powf(1.25)
        }
    };

    let s2 = |i: f64| -> f64 {
        if i == 0. {
            0.
        } else if i >= 2. * x4 {
            1.
        } else if i < x4 {
            0.5 * (i / x4).powf(1.25)
        } else {
            1. - 0.5 * (2. - i / x4).powf(1.25)
        }
    };

    let unit_hydrograph_1 = (1..=x4.ceil() as usize)
        .map(|i| s1(i as f64) - s1(i as f64 - 1.))
        .collect();
    let unit_hydrograph_2 = (1..=(2. * x4).ceil() as usize)
        .map(|i| s2(i as f64) - s2(i as f64 - 1.))
        .collect();

    (unit_hydrograph_1, unit_hydrograph_2)
}

fn update_production(
    store: &mut f64,
    routing_precipitation: &mut f64,
    precipitation: f64,
    pet: f64,
    x1: f64,
) {
    let mut store_precipitation: f64 = 0.0;
    let mut net_precipitation: f64 = 0.0;
    if precipitation > pet {
        net_precipitation = precipitation - pet;
        // only calculate terms once
        let tmp_term_1 = *store / x1;
        let tmp_term_2 = (net_precipitation / x1).tanh();

        store_precipitation = x1 * (1. - tmp_term_1 * tmp_term_1) * tmp_term_2
            / (1. + tmp_term_1 * tmp_term_2);
        *store += store_precipitation;
    } else if precipitation < pet {
        let net_pet = pet - precipitation;
        // only calculate terms once
        let tmp_term_1 = *store / x1;
        let tmp_term_2 = (net_pet / x1).tanh();
        let evapotranspiration = *store * (2. - tmp_term_1) * tmp_term_2
            / (1. + (1. - tmp_term_1) * tmp_term_2);
        *store -= evapotranspiration;
    }

    let mut percolation = 0.0;
    if x1 / *store > 1e-3 {
        percolation = *store
            * (1. - (1. + (4. / 21. * *store / x1).powi(4)).powf(-0.25));
        *store -= percolation;
    }

    *routing_precipitation =
        net_precipitation - store_precipitation + percolation;
}

fn update_routing(
    store: &mut f64,
    hydrographs: &mut (Vec<f64>, Vec<f64>),
    total_flow: &mut f64,
    unit_hydrographs: &(Vec<f64>, Vec<f64>),
    routing_precipitation: f64,
    x2: f64,
    x3: f64,
) {
    update_hydrographs(routing_precipitation, hydrographs, unit_hydrographs);

    let q9 = hydrographs.0[0];
    let q1 = hydrographs.1[0];

    let groundwater_exchange = x2 * (*store / x3).powf(3.5);

    *store = (*store + q9 + groundwater_exchange).max(1e-3 * x3);

    let routed_flow = *store * (1. - (1. + (*store / x3).powi(4)).powf(-0.25));
    *store -= routed_flow;

    let direct_flow = (q1 + groundwater_exchange).max(0.);

    *total_flow = routed_flow + direct_flow;
}

fn update_hydrographs(
    routing_precipitation: f64,
    hydrographs: &mut (Vec<f64>, Vec<f64>),
    unit_hydrographs: &(Vec<f64>, Vec<f64>),
) {
    let n1 = hydrographs.0.len();
    for i in 0..n1 - 1 {
        hydrographs.0[i] = hydrographs.0[i + 1]
            + 0.9 * routing_precipitation * unit_hydrographs.0[i];
    }
    hydrographs.0[n1 - 1] =
        0.9 * routing_precipitation * unit_hydrographs.0[n1 - 1];

    let n2 = hydrographs.1.len();
    for i in 0..n2 - 1 {
        hydrographs.1[i] = hydrographs.1[i + 1]
            + 0.1 * routing_precipitation * unit_hydrographs.1[i];
    }
    hydrographs.1[n2 - 1] =
        0.1 * routing_precipitation * unit_hydrographs.1[n2 - 1];
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
    let m = PyModule::new(py, "gr4j")?;
    m.add("param_names", param_names)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
