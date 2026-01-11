use ndarray::{array, Array1, Array2, ArrayView1, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

use crate::snow::utils::{
    check_lengths, validate_day_of_year, validate_inputs_finite,
    validate_non_negative, validate_output, validate_parameter,
    validate_temperature, SnowError,
};

pub const param_names: &[&str] = &["ctg", "kf", "qnbv"];

const BOUNDS: [(&str, f64, f64); 3] =
    [("ctg", 0.0, 1.0), ("kf", 0.0, 20.0), ("qnbv", 50.0, 800.0)];

const TOLERANCE: f64 = 1e-10;

pub fn init() -> (Array1<f64>, Array2<f64>) {
    // corresponds to ctg, kf, qnbv
    let default_values = array![0.25, 3.74, 350.0];
    let bounds = array![
        [BOUNDS[0].1, BOUNDS[0].2],
        [BOUNDS[1].1, BOUNDS[1].2],
        [BOUNDS[2].1, BOUNDS[2].2]
    ];
    (default_values, bounds)
}

pub fn simulate(
    params: ArrayView1<f64>,
    precipitation: ArrayView1<f64>,
    temperature: ArrayView1<f64>,
    day_of_year: ArrayView1<usize>,
    elevation_layers: ArrayView1<f64>,
    median_elevation: f64,
) -> Result<Array1<f64>, SnowError> {
    let [ctg, kf, qnbv]: [f64; 3] = params
        .as_slice()
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| SnowError::ParamsMismatch(3, params.len()))?;

    for (i, &param_value) in [ctg, kf, qnbv].iter().enumerate() {
        let (name, lower, upper) = BOUNDS[i];
        validate_parameter(param_value, name, lower, upper)?;
    }

    check_lengths(precipitation, temperature, day_of_year)?;
    validate_inputs_finite(precipitation, "precipitation")?;
    validate_non_negative(precipitation, "precipitation")?;
    validate_temperature(temperature)?;
    validate_day_of_year(day_of_year)?;
    validate_inputs_finite(elevation_layers, "elevation_layers")?;

    let beta = 0.0;
    let vmin = 0.1;
    let tf = 0.0;
    let n_layers = elevation_layers.len();
    let g_threshold = qnbv * 0.9;
    let n_timesteps = precipitation.len();

    let elevation_offsets: Vec<f64> = elevation_layers
        .iter()
        .map(|&z| (z - median_elevation) / 100.0)
        .collect();

    let precip_weights: Vec<f64> = elevation_layers
        .iter()
        .map(|&z| (beta * (z - median_elevation)).exp())
        .collect();
    let normalization: f64 = precip_weights.iter().sum();

    if normalization.abs() < TOLERANCE {
        return Err(SnowError::NumericalError {
            context: "CemaNeige precipitation normalization",
            detail: "sum of precipitation weights is zero".to_string(),
        });
    }

    let mut effective_precipitation: Vec<f64> = vec![0.0; n_timesteps];

    let mut snowpack: Vec<f64> = vec![0.0; n_layers];
    let mut thermal_state: Vec<f64> = vec![0.0; n_layers];

    let mut layer_temp: Vec<f64> = vec![0.0; n_layers];

    Zip::indexed(&precipitation)
        .and(&temperature)
        .and(&day_of_year)
        .for_each(|t, &precip_t, &temp_t, &doy| {
            let theta = TEMPERATURE_GRADIENT[(doy - 1) % 365];

            let mut total_liquid: f64 = 0.0;
            let mut total_melt: f64 = 0.0;

            for i in 0..n_layers {
                let layer_temperature = elevation_offsets[i] * theta + temp_t;
                layer_temp[i] = layer_temperature;

                let layer_precip =
                    precip_t * precip_weights[i] / normalization;

                let solid_fraction = if layer_temperature > 3.0 {
                    0.0
                } else if layer_temperature < -1.0 {
                    1.0
                } else {
                    1.0 - (layer_temperature + 1.0) / 4.0
                };

                let p_solid = solid_fraction * layer_precip;
                let p_liquid = layer_precip - p_solid;
                total_liquid += p_liquid;

                snowpack[i] += p_solid;

                thermal_state[i] = (thermal_state[i] * ctg
                    + layer_temperature * (1.0 - ctg))
                    .min(0.0);
            }

            for i in 0..n_layers {
                let layer_temperature = layer_temp[i];

                let potential =
                    if thermal_state[i] >= tf && layer_temperature > 0.0 {
                        let max_melt = (layer_temperature - tf) * kf;
                        snowpack[i].min(max_melt)
                    } else {
                        0.0
                    };

                let fnts = (snowpack[i] / g_threshold).min(1.0);
                let melt_factor = fnts * (1.0 - vmin) + vmin;

                let snow_melt = potential * melt_factor;
                snowpack[i] -= snow_melt;
                total_melt += snow_melt;
            }

            effective_precipitation[t] = total_liquid + total_melt;
        });

    let result = Array1::from_vec(effective_precipitation);

    validate_output(result.view(), "CemaNeige simulation")?;

    Ok(result)
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
    temperature: PyReadonlyArray1<f64>,
    day_of_year: PyReadonlyArray1<usize>,
    elevation_layers: PyReadonlyArray1<f64>,
    median_elevation: f64,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let simulation = simulate(
        params.as_array(),
        precipitation.as_array(),
        temperature.as_array(),
        day_of_year.as_array(),
        elevation_layers.as_array(),
        median_elevation,
    )?;
    Ok(simulation.to_pyarray(py))
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "cemaneige")?;
    m.add("param_names", param_names)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}

#[allow(clippy::approx_constant)]
const TEMPERATURE_GRADIENT: [f64; 365] = [
    -0.376, -0.374, -0.371, -0.368, -0.366, -0.363, -0.361, -0.358, -0.355,
    -0.353, -0.350, -0.348, -0.345, -0.343, -0.340, -0.337, -0.335, -0.332,
    -0.329, -0.327, -0.324, -0.321, -0.319, -0.316, -0.313, -0.311, -0.308,
    -0.305, -0.303, -0.300, -0.297, -0.295, -0.292, -0.289, -0.287, -0.284,
    -0.281, -0.279, -0.276, -0.273, -0.271, -0.268, -0.265, -0.263, -0.260,
    -0.262, -0.264, -0.266, -0.268, -0.270, -0.272, -0.274, -0.277, -0.279,
    -0.281, -0.283, -0.285, -0.287, -0.289, -0.291, -0.293, -0.295, -0.297,
    -0.299, -0.301, -0.303, -0.306, -0.308, -0.310, -0.312, -0.314, -0.316,
    -0.318, -0.320, -0.323, -0.326, -0.330, -0.333, -0.336, -0.339, -0.343,
    -0.346, -0.349, -0.352, -0.355, -0.359, -0.362, -0.365, -0.368, -0.372,
    -0.375, -0.378, -0.381, -0.385, -0.388, -0.391, -0.394, -0.397, -0.401,
    -0.404, -0.407, -0.410, -0.414, -0.417, -0.420, -0.420, -0.421, -0.421,
    -0.421, -0.422, -0.422, -0.422, -0.423, -0.423, -0.423, -0.424, -0.424,
    -0.424, -0.425, -0.425, -0.425, -0.426, -0.426, -0.426, -0.427, -0.427,
    -0.427, -0.428, -0.428, -0.428, -0.429, -0.429, -0.429, -0.430, -0.430,
    -0.428, -0.425, -0.423, -0.421, -0.419, -0.416, -0.414, -0.412, -0.410,
    -0.407, -0.405, -0.403, -0.401, -0.398, -0.396, -0.394, -0.392, -0.389,
    -0.387, -0.385, -0.383, -0.380, -0.378, -0.376, -0.374, -0.371, -0.369,
    -0.367, -0.365, -0.362, -0.360, -0.362, -0.365, -0.367, -0.369, -0.372,
    -0.374, -0.376, -0.379, -0.381, -0.383, -0.386, -0.388, -0.390, -0.393,
    -0.395, -0.397, -0.400, -0.402, -0.404, -0.407, -0.409, -0.411, -0.414,
    -0.416, -0.418, -0.421, -0.423, -0.425, -0.428, -0.430, -0.431, -0.431,
    -0.432, -0.433, -0.433, -0.434, -0.435, -0.435, -0.436, -0.436, -0.437,
    -0.438, -0.438, -0.439, -0.440, -0.440, -0.441, -0.442, -0.442, -0.443,
    -0.444, -0.444, -0.445, -0.445, -0.446, -0.447, -0.447, -0.448, -0.449,
    -0.449, -0.450, -0.448, -0.447, -0.445, -0.444, -0.442, -0.440, -0.439,
    -0.437, -0.435, -0.434, -0.432, -0.431, -0.429, -0.427, -0.426, -0.424,
    -0.423, -0.421, -0.419, -0.418, -0.416, -0.415, -0.413, -0.411, -0.410,
    -0.408, -0.406, -0.405, -0.403, -0.402, -0.400, -0.403, -0.405, -0.408,
    -0.411, -0.413, -0.416, -0.419, -0.421, -0.424, -0.427, -0.429, -0.432,
    -0.435, -0.437, -0.440, -0.443, -0.445, -0.448, -0.451, -0.453, -0.456,
    -0.459, -0.461, -0.464, -0.467, -0.469, -0.472, -0.475, -0.477, -0.480,
    -0.482, -0.483, -0.485, -0.486, -0.488, -0.490, -0.491, -0.493, -0.495,
    -0.496, -0.498, -0.499, -0.501, -0.503, -0.504, -0.506, -0.507, -0.509,
    -0.511, -0.512, -0.514, -0.515, -0.517, -0.519, -0.520, -0.522, -0.524,
    -0.525, -0.527, -0.528, -0.530, -0.526, -0.523, -0.519, -0.515, -0.512,
    -0.508, -0.504, -0.501, -0.497, -0.493, -0.490, -0.486, -0.482, -0.479,
    -0.475, -0.471, -0.468, -0.464, -0.460, -0.457, -0.453, -0.449, -0.446,
    -0.442, -0.438, -0.435, -0.431, -0.427, -0.424, -0.420, -0.417, -0.415,
    -0.412, -0.410, -0.407, -0.405, -0.402, -0.399, -0.397, -0.394, -0.392,
    -0.389, -0.386, -0.384, -0.381, -0.379,
];
