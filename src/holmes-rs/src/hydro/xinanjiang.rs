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
    "Flow partitioning coefficient between fast and slow routing (-)",
    "Fast routing reservoir emptying constant (d)",
    "Slow routing reservoir emptying multiplier (-)",
    "Free-water reservoir capacity (mm)",
    "Soil reservoir capacity (mm)",
    "Unit hydrograph delay (d)",
    "Free-water reservoir emptying constant (d)",
    "Free-water saturation-excess distribution exponent (-)",
];

// Lower bounds on x2, x3 and x7 are tightened relative to HOOPLA (which allows
// values below one) so that T -= T/x2, M -= M/(x2*x3) and R -= R/x7 can never
// drive the reservoir states negative; with x2 >= 1, x3 >= 1 and x7 >= 1 each
// drawdown ratio stays in [0, 1].
const BOUNDS: [(&str, f64, f64); 8] = [
    ("x1", 0.01, 0.99),
    ("x2", 1.0, 20.0),
    ("x3", 1.0, 50.0),
    ("x4", 1.0, 500.0),
    ("x5", 1.0, 2000.0),
    ("x6", 0.5, 10.0),
    ("x7", 1.0, 50.0),
    ("x8", 0.01, 5.0),
];

// Fixed soil-reservoir saturation-excess exponent (Perrin fixes B = 0.25).
const XF1: f64 = 0.25;

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

    let (mut s, mut r, mut t, mut m, dl, mut hy) = init_state(x5, x6);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x4, x5, x7, x8, &mut s, &mut r,
                &mut t, &mut m, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);

    validate_output(result.view(), "XINANJIANG simulation")?;

    Ok(result)
}

fn init_state(
    x5: f64,
    x6: f64,
) -> (f64, f64, f64, f64, Array1<f64>, Array1<f64>) {
    // Initial reservoir states from HOOPLA ini_HydroMod20.m:
    //   S seeded at the soil capacity x5, R/T/M seeded at small warm-start values.
    let s = x5;
    let r = 1.0;
    let t = 5.0;
    let m = 400.0;

    // Two-tap delay unit hydrograph controlled by x6 (fractional delay):
    //   the last two ordinates share the mass, all earlier ordinates are zero.
    let size = x6.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x6 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];

    let hy = Array1::zeros(size);

    (s, r, t, m, dl, hy)
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
    s: &mut f64,
    r: &mut f64,
    t: &mut f64,
    m: &mut f64,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    let pn = (p - e).max(0.0);
    let en = (e - p).max(0.0);

    let mut qs0 = 0.0;
    let mut ir = 0.0;

    if en > 0.0 {
        // Soil-moisture ET with piecewise rate dropping at low saturation.
        let ratio = *s / x5;
        let es = if ratio >= 0.9 {
            s.min(en)
        } else if ratio < 0.09 {
            s.min(en * 0.1)
        } else {
            s.min(en * *s / (0.9 * x5))
        };
        *s -= es;
    } else if pn > 0.0 {
        // Soil reservoir: saturation-excess via a fixed-shape (B = 0.25)
        // spatial distribution of retention capacities.
        let base_s = (1.0 - *s / x5).max(0.0);
        let fs_raw = base_s.powf(1.0 / (1.0 + XF1)) - pn / ((1.0 + XF1) * x5);
        let fs = fs_raw.max(0.0).powf(1.0 + XF1);
        let ps = (x5 - *s - fs * x5).max(0.0);
        *s = (*s + ps).min(x5);

        // Free-water reservoir: Zhao-style saturation-excess runoff above the
        // fillable fraction of R, with shape exponent x8.
        let pr = (pn - ps).max(0.0);
        let base_r = (1.0 - *r / x4).max(0.0);
        let fr_raw = base_r.powf(1.0 / (1.0 + x8)) - pr / ((1.0 + x8) * x4);
        let fr = fr_raw.max(0.0).powf(1.0 + x8);
        let pr2 = (x4 - *r - fr * x4).max(0.0);
        *r = (*r + pr2).min(x4);

        qs0 = (pr - pr2).max(0.0);
        ir = *r / x7;
    }

    // Routing: drain R into split fast/slow linear reservoirs.
    *r -= ir;
    *t += ir * x1;
    let qt = *t / x2;
    *t -= qt;
    *m += ir * (1.0 - x1);
    let qm = *m / (x2 * x3);
    *m -= qm;

    // Unit-hydrograph shift-and-add convolution on the aggregated flow.
    let n = hy.len();
    let q = qs0 + qt + qm;
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * q;
    }
    hy[n - 1] = dl[n - 1] * q;

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
    let m = PyModule::new(py, "xinanjiang")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
