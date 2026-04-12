use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative,
    validate_output, validate_parameter, HydroError,
};
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

pub const param_names: &[&str] =
    &["x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "x9", "x10"];

pub const param_descriptions: &[&str] = &[
    "Emptying threshold of the ground reservoir (mm)",
    "Emptying constant of routing reservoirs (d)",
    "Sub-surface flow constant (-)",
    "Delay (d)",
    "Percolation constant (-)",
    "Emptying constant of the ground reservoir (d)",
    "Maximum capacity of the soil reservoir (mm)",
    "Surface flow constant (-)",
    "Maximum capacity of the surface reservoir (mm)",
    "Capillary rise parameter (mm)",
];

// Lower bounds on x2, x3, x6, x8 are >= 1 so that linear outflows of
// the form q = storage / x can never exceed the stored volume, which
// keeps every reservoir non-negative by construction. x5 is strictly
// below 1 because the percolation formula divides by (1 - x5).
const BOUNDS: [(&str, f64, f64); 10] = [
    ("x1", 1.0, 1000.0),
    ("x2", 1.0, 100.0),
    ("x3", 1.0, 100.0),
    ("x4", 0.5, 10.0),
    ("x5", 0.01, 0.99),
    ("x6", 1.0, 500.0),
    ("x7", 1.0, 1000.0),
    ("x8", 1.0, 100.0),
    ("x9", 1.0, 1000.0),
    ("x10", 0.01, 10.0),
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
        [BOUNDS[9].1, BOUNDS[9].2],
    ];
    let default_values = bounds.sum_axis(Axis(1)) / 2.0;
    (default_values, bounds)
}

// NAM keeps seven reservoirs alive between time steps. They are bundled
// in a struct because passing seven `&mut f64` to run_step would trip
// clippy::too_many_arguments and obscure the data flow.
//
// `gw` is a soil-moisture *deficit*: smaller means wetter, and recharge
// from the production phase is *subtracted* from gw. The whole baseflow
// branch only makes sense with this convention in mind.
struct State {
    u: f64,
    l: f64,
    ck1: f64,
    ck1b: f64,
    ck2: f64,
    ck2b: f64,
    gw: f64,
}

pub fn simulate(
    params: ArrayView1<f64>,
    precipitation: ArrayView1<f64>,
    pet: ArrayView1<f64>,
) -> Result<Array1<f64>, HydroError> {
    let [x1, x2, x3, x4, x5, x6, x7, x8, x9, x10]: [f64; 10] = params
        .as_slice()
        .and_then(|s| s.try_into().ok())
        .ok_or_else(|| HydroError::ParamsMismatch(10, params.len()))?;

    for (i, &param_value) in
        [x1, x2, x3, x4, x5, x6, x7, x8, x9, x10].iter().enumerate()
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

    let (mut state, dl, mut hy) = init_state(x4, x7, x9);

    Zip::indexed(&precipitation)
        .and(&pet)
        .for_each(|i, &precip_t, &pet_t| {
            streamflow[i] = run_step(
                precip_t, pet_t, x1, x2, x3, x5, x6, x7, x8, x9, x10,
                &mut state, &dl, &mut hy,
            );
        });

    let result = Array1::from_vec(streamflow);
    validate_output(result.view(), "NAM simulation")?;
    Ok(result)
}

fn init_state(x4: f64, x7: f64, x9: f64) -> (State, Array1<f64>, Array1<f64>) {
    // Initial reservoir states from HOOPLA ini_HydroMod12.m. The
    // ground-water deficit gw starts at 50 mm so the (x10 / gw)^2
    // capillary-rise term has a finite, well-conditioned value on
    // the very first wet day.
    let state = State {
        u: x9,
        l: x7 * 0.5,
        ck1: 0.0,
        ck1b: 0.0,
        ck2: 0.0,
        ck2b: 0.0,
        gw: 50.0,
    };

    // Fractional-delay routing, identical construction to GR4J,
    // GARDENIA and SACRAMENTO: dl[n-2] carries the fractional part
    // of x4 and dl[n-1] the complement. Mirrors HOOPLA's
    //   DL(end-1) = 1/(x4 - k(end-1) + 1)
    //   DL(end)   = 1 - DL(end-1)
    // verbatim — see ini_HydroMod12.m.
    let size = x4.ceil() as usize + 1;
    let mut dl = Array1::zeros(size);
    dl[size - 2] = 1.0 / (x4 - size as f64 + 3.0);
    dl[size - 1] = 1.0 - dl[size - 2];
    let hy = Array1::zeros(size);

    (state, dl, hy)
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
    x9: f64,
    x10: f64,
    state: &mut State,
    dl: &Array1<f64>,
    hy: &mut Array1<f64>,
) -> f64 {
    // ----- Interflow extraction and interflow cascade -----
    // Surface reservoir absorbs rainfall, then loses interflow QIF
    // proportional to the soil filling ratio L/x7. The interflow
    // then cascades through two linear reservoirs (CK1 -> CK2)
    // before reaching the channel as B2.
    state.u += p;
    let qif = state.u.min(state.l / x7 * state.u / x3);
    state.u -= qif;
    state.ck1 += qif;
    let b21 = state.ck1 / x2;
    state.ck1 -= b21;
    state.ck2 += b21;
    let b2 = state.ck2 / x2;
    state.ck2 -= b2;

    // ----- Surface evapotranspiration with three-branch logic -----
    // After E is debited, the surface store is in one of three
    // states: (a) within capacity -> no overflow, no residual PET;
    // (b) emptied -> residual PET demand E1 is forwarded to the soil
    // store; (c) overflowed -> the spill PN feeds the production
    // phase below.
    state.u -= e;
    let (e1, pn) = if state.u >= 0.0 && state.u <= x9 {
        (0.0, 0.0)
    } else if state.u < 0.0 {
        let e1 = -state.u;
        state.u = 0.0;
        (e1, 0.0)
    } else {
        let pn = state.u - x9;
        state.u = x9;
        (0.0, pn)
    };

    // ----- Overland-flow partitioning of the spill PN -----
    // PN is split into overland flow QOF, groundwater recharge G
    // (only when soil is wetter than the percolation threshold x5),
    // and soil-store recharge DL0. When DL0 exceeds soil capacity
    // the surplus is forced into G via DL1.
    //
    // The HOOPLA Matlab also has an `if x(5) == 1` short-circuit
    // setting G = 0; the bounds keep x5 <= 0.99 so that branch is
    // unreachable here and is intentionally omitted.
    let mut qof = 0.0;
    let mut dl0 = 0.0;
    let mut g = 0.0;
    if pn > 0.0 {
        qof = pn * state.l / x7 / x8;
        if state.l / x7 > x5 {
            g = (pn - qof) * (state.l / x7 - x5) / (1.0 - x5);
        }
        dl0 = pn - qof - g;
        // Bookkeeping subtlety: DL0 is *not* decremented when the
        // surplus DL1 is added to G. Instead, the soil store
        // temporarily over-fills (L = L + DL0 below), and the
        // explicit `if L > x7` clip removes exactly DL1 worth of
        // water. So DL1 appears once as recharge to G and once as
        // over-spill from L, and total mass is conserved. Verbatim
        // port of HOOPLA HM12 — do not "fix" without re-deriving.
        if dl0 > x7 {
            let dl1 = dl0 - (x7 - state.l);
            g += dl1;
        }
    }

    // ----- Overland cascade (CK1b -> CK2b) -----
    state.ck1b += qof;
    let b12 = state.ck1b / x2;
    state.ck1b -= b12;
    state.ck2b += b12;
    let b1 = state.ck2b / x2;
    state.ck2b -= b1;

    // ----- Soil reservoir update -----
    // Recharge from spill, then evaporate the residual PET demand
    // proportional to the soil filling ratio. Clamped to zero so a
    // very dry soil cannot pull L below the physical floor.
    state.l += dl0;
    state.l = (state.l - e1 * state.l / x7).max(0.0);

    // ----- Groundwater (deficit variable) and baseflow -----
    // gw carries a *deficit*, so subtracting recharge G *reduces*
    // the deficit. When the deficit drops below the threshold x1,
    // baseflow starts: BF closes the gap toward x1 over the time
    // constant x6. The BF1 branch is an emergency reset that
    // prevents the (x10/gw)^2 capillary term from dividing by
    // zero — if gw would become non-positive after baseflow, we
    // clamp it to 0.1 and route the surplus through BF1.
    state.gw -= g;
    let bf = if state.gw <= x1 {
        (x1 - state.gw) / x6
    } else {
        0.0
    };
    state.gw += bf;

    let bf1 = if state.gw > 0.0 {
        0.0
    } else {
        let surplus = -state.gw + 0.1;
        state.gw = 0.1;
        surplus
    };

    // Cap soil at its capacity. The earlier "DL0 > x7" branch may
    // leave L overshooting; this clip is what makes the bookkeeping
    // mass-conservative (see comment in the production block).
    if state.l > x7 {
        state.l = x7;
    }

    // ----- Capillary rise from groundwater into soil -----
    // Driven by the soil-deficit ratio sqrt(1 - L/x7) and damped by
    // the squared groundwater-deficit ratio (x10/gw)^2. Capped at
    // the free capacity of the soil store so it never overshoots.
    let mut caflu = (1.0 - state.l / x7).sqrt() * (x10 / state.gw).powi(2);
    if caflu > x7 - state.l {
        caflu = x7 - state.l;
    }
    state.l += caflu;
    state.gw += caflu;

    // ----- Total discharge through the unit hydrograph -----
    // Channel inflow is the sum of the four cascade outputs
    // (BF + BF1 + B1 + B2), routed through the fractional-delay UH.
    // Equivalent to HOOPLA's
    //   HY = [HY(2:end); 0] + DL * (BF + BF1 + B1 + B2)
    let qtot = bf + bf1 + b1 + b2;
    let n = hy.len();
    for i in 0..n - 1 {
        hy[i] = hy[i + 1] + dl[i] * qtot;
    }
    hy[n - 1] = dl[n - 1] * qtot;

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
    let m = PyModule::new(py, "nam")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
