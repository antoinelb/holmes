#![allow(clippy::too_many_arguments)]
#![allow(clippy::type_complexity)]

use ndarray::{s, Array1, ArrayView1};
use ndarray_rand::rand_distr::StandardNormal;
use numpy::{PyArray1, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;
use rand::{Rng, SeedableRng};
use rand_chacha::ChaCha8Rng;
use std::str::FromStr;

use crate::calibration::utils::{
    build_simulate, evaluate_simulation, worst_case_objectives,
    CalibrationError, CalibrationParams, Objective, Transformation,
};

struct DdsParams {
    pub r: f64,
    pub max_evaluations: usize,
    pub n_calls: usize,
    pub best_objectives: Array1<f64>,
    // Cached simulation of the incumbent best. DDS runs the model exactly
    // once per step, so re-simulating the best on every return (as SCE does)
    // would double the real cost of a calibration.
    pub best_simulation: Array1<f64>,
}

/// Dynamically Dimensioned Search (Tolson & Shoemaker, 2007,
/// doi:10.1029/2005WR004723): single-solution greedy stochastic search whose
/// perturbation schedule is scaled to the evaluation budget.
#[pyclass(module = "holmes_rs.calibration.dds")]
pub struct Dds {
    calibration_params: CalibrationParams,
    dds_params: DdsParams,
}

impl Dds {
    pub fn new(
        hydro_model: &str,
        snow_model: Option<&str>,
        objective: Objective,
        transformation: Transformation,
        r: f64,
        max_evaluations: usize,
        seed: u64,
    ) -> Result<Self, CalibrationError> {
        if !r.is_finite() || r <= 0.0 || r > 1.0 {
            return Err(CalibrationError::InvalidParameter(format!(
                "neighborhood size r must be in (0, 1], got {r}"
            )));
        }
        // The perturbation probability is 1 - ln(i)/ln(m): with m = 1,
        // ln(m) = 0 divides by zero, and a 1-evaluation budget would be the
        // initial point alone anyway.
        if max_evaluations < 2 {
            return Err(CalibrationError::InvalidParameter(format!(
                "max_evaluations must be at least 2, got {max_evaluations}"
            )));
        }

        let (simulate, _defaults, bounds) =
            build_simulate(hydro_model, snow_model)?;

        let lower_bounds: Array1<f64> = bounds.column(0).to_owned();
        let upper_bounds: Array1<f64> = bounds.column(1).to_owned();

        let rng = ChaCha8Rng::seed_from_u64(seed);

        let params = midpoint(&lower_bounds, &upper_bounds);

        let calibration_params = CalibrationParams {
            params,
            simulate,
            lower_bounds,
            upper_bounds,
            objective,
            transformation,
            rng,
            done: false,
        };
        let dds_params = DdsParams {
            r,
            max_evaluations,
            n_calls: 0,
            best_objectives: worst_case_objectives(),
            best_simulation: Array1::from_vec(vec![]),
        };

        Ok(Dds {
            calibration_params,
            dds_params,
        })
    }

    pub fn init(
        &mut self,
        precipitation: ArrayView1<f64>,
        temperature: Option<ArrayView1<f64>>,
        pet: ArrayView1<f64>,
        day_of_year: Option<ArrayView1<usize>>,
        elevation_bands: Option<ArrayView1<f64>>,
        median_elevation: Option<f64>,
        observations: ArrayView1<f64>,
        warmup_steps: usize,
    ) -> Result<(), CalibrationError> {
        // Fail fast and clearly if the whole window is empty, mirroring SCE.
        if !observations
            .slice(s![warmup_steps..])
            .iter()
            .any(|o| o.is_finite())
        {
            return Err(CalibrationError::NoObservations);
        }

        // Deterministic initial solution: the midpoint of the bounds, matching
        // the first member of SCE's initial population. Recomputed here so a
        // re-init fully resets the search state.
        let params = midpoint(
            &self.calibration_params.lower_bounds,
            &self.calibration_params.upper_bounds,
        );

        let simulation = (self.calibration_params.simulate)(
            params.view(),
            precipitation,
            temperature,
            pet,
            day_of_year,
            elevation_bands,
            median_elevation,
        )?;
        let objectives = evaluate_simulation(
            observations,
            simulation.view(),
            self.calibration_params.transformation,
            warmup_steps,
        )?;

        self.calibration_params.params = params;
        self.calibration_params.done = false;
        self.dds_params.best_objectives = objectives;
        self.dds_params.best_simulation = simulation;
        self.dds_params.n_calls = 1;

        Ok(())
    }

    pub fn step(
        &mut self,
        precipitation: ArrayView1<f64>,
        temperature: Option<ArrayView1<f64>>,
        pet: ArrayView1<f64>,
        day_of_year: Option<ArrayView1<usize>>,
        elevation_bands: Option<ArrayView1<f64>>,
        median_elevation: Option<f64>,
        observations: ArrayView1<f64>,
        warmup_steps: usize,
    ) -> Result<(bool, Array1<f64>, Array1<f64>, Array1<f64>), CalibrationError>
    {
        if self.calibration_params.done {
            return Ok((
                true,
                self.calibration_params.params.clone(),
                self.dds_params.best_simulation.clone(),
                self.dds_params.best_objectives.clone(),
            ));
        }

        let (objective_idx, is_minimization) =
            match self.calibration_params.objective {
                Objective::Rmse => (0, true),
                Objective::Nse => (1, false),
                Objective::Kge => (2, false),
            };

        // Perturbation probability decays with the fraction of the budget
        // already spent: early steps move most parameters (global search),
        // late steps move roughly one (local refinement).
        let inclusion_probability = 1.0
            - (self.dds_params.n_calls as f64).ln()
                / (self.dds_params.max_evaluations as f64).ln();

        let candidate = perturb_candidate(
            self.calibration_params.params.view(),
            self.calibration_params.lower_bounds.view(),
            self.calibration_params.upper_bounds.view(),
            self.dds_params.r,
            inclusion_probability,
            &mut self.calibration_params.rng,
        );

        let simulation = (self.calibration_params.simulate)(
            candidate.view(),
            precipitation,
            temperature,
            pet,
            day_of_year,
            elevation_bands,
            median_elevation,
        )?;
        let objectives = evaluate_simulation(
            observations,
            simulation.view(),
            self.calibration_params.transformation,
            warmup_steps,
        )?;
        self.dds_params.n_calls += 1;

        // Greedy acceptance; ties accepted, per the paper's F(x_new) <= F_best.
        let old = self.dds_params.best_objectives[objective_idx];
        let new = objectives[objective_idx];
        let accepted = if is_minimization {
            new <= old
        } else {
            new >= old
        };
        if accepted {
            self.calibration_params.params = candidate;
            self.dds_params.best_objectives = objectives;
            self.dds_params.best_simulation = simulation;
        }

        self.calibration_params.done =
            self.dds_params.n_calls >= self.dds_params.max_evaluations;

        Ok((
            self.calibration_params.done,
            self.calibration_params.params.clone(),
            self.dds_params.best_simulation.clone(),
            self.dds_params.best_objectives.clone(),
        ))
    }
}

#[cfg_attr(coverage_nightly, coverage(off))]
#[pymethods]
impl Dds {
    #[new]
    pub fn py_new(
        hydro_model: &str,
        snow_model: Option<&str>,
        objective: &str,
        transformation: &str,
        r: f64,
        max_evaluations: usize,
        seed: u64,
    ) -> PyResult<Self> {
        let objective = Objective::from_str(objective)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        let transformation = Transformation::from_str(transformation)
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        Dds::new(
            hydro_model,
            snow_model,
            objective,
            transformation,
            r,
            max_evaluations,
            seed,
        )
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    #[pyo3(name = "init")]
    pub fn py_init(
        &mut self,
        py: Python<'_>,
        precipitation: PyReadonlyArray1<f64>,
        temperature: Option<PyReadonlyArray1<f64>>,
        pet: PyReadonlyArray1<f64>,
        day_of_year: Option<PyReadonlyArray1<usize>>,
        elevation_bands: Option<PyReadonlyArray1<f64>>,
        median_elevation: Option<f64>,
        observations: PyReadonlyArray1<'_, f64>,
        warmup_steps: usize,
    ) -> PyResult<()> {
        let precipitation = precipitation.as_array().to_owned();
        let temperature = temperature.map(|t| t.as_array().to_owned());
        let pet = pet.as_array().to_owned();
        let day_of_year = day_of_year.map(|d| d.as_array().to_owned());
        let elevation_bands = elevation_bands.map(|e| e.as_array().to_owned());
        let observations = observations.as_array().to_owned();
        py.detach(|| {
            self.init(
                precipitation.view(),
                temperature.as_ref().map(|t| t.view()),
                pet.view(),
                day_of_year.as_ref().map(|d| d.view()),
                elevation_bands.as_ref().map(|e| e.view()),
                median_elevation,
                observations.view(),
                warmup_steps,
            )
        })
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    #[pyo3(name = "step")]
    pub fn py_step<'py>(
        &mut self,
        py: Python<'py>,
        precipitation: PyReadonlyArray1<f64>,
        temperature: Option<PyReadonlyArray1<f64>>,
        pet: PyReadonlyArray1<f64>,
        day_of_year: Option<PyReadonlyArray1<usize>>,
        elevation_bands: Option<PyReadonlyArray1<f64>>,
        median_elevation: Option<f64>,
        observations: PyReadonlyArray1<'_, f64>,
        warmup_steps: usize,
    ) -> PyResult<(
        bool,
        Bound<'py, PyArray1<f64>>,
        Bound<'py, PyArray1<f64>>,
        Bound<'py, PyArray1<f64>>,
    )> {
        let precipitation = precipitation.as_array().to_owned();
        let temperature = temperature.map(|t| t.as_array().to_owned());
        let pet = pet.as_array().to_owned();
        let day_of_year = day_of_year.map(|d| d.as_array().to_owned());
        let elevation_bands = elevation_bands.map(|e| e.as_array().to_owned());
        let observations = observations.as_array().to_owned();
        let (done, best_params, simulation, objectives) = py
            .detach(|| {
                self.step(
                    precipitation.view(),
                    temperature.as_ref().map(|t| t.view()),
                    pet.view(),
                    day_of_year.as_ref().map(|d| d.view()),
                    elevation_bands.as_ref().map(|e| e.view()),
                    median_elevation,
                    observations.view(),
                    warmup_steps,
                )
            })
            .map_err(|e| {
                pyo3::exceptions::PyValueError::new_err(e.to_string())
            })?;
        Ok((
            done,
            best_params.to_pyarray(py),
            simulation.to_pyarray(py),
            objectives.to_pyarray(py),
        ))
    }
}

fn midpoint(
    lower_bounds: &Array1<f64>,
    upper_bounds: &Array1<f64>,
) -> Array1<f64> {
    Array1::from_iter(
        lower_bounds
            .iter()
            .zip(upper_bounds)
            .map(|(l, u)| (l + u) / 2.),
    )
}

/// Build a DDS candidate: each dimension of the incumbent is selected with
/// `inclusion_probability` (at least one is always selected, per the paper)
/// and perturbed by a normal step with standard deviation `r` times the bound
/// range, reflected at the bounds.
/// Exposed for unit tests; use `Dds::step` from calling code.
pub fn perturb_candidate(
    best: ArrayView1<f64>,
    lower_bounds: ArrayView1<f64>,
    upper_bounds: ArrayView1<f64>,
    r: f64,
    inclusion_probability: f64,
    rng: &mut ChaCha8Rng,
) -> Array1<f64> {
    let n_params = best.len();

    let mut selected: Vec<usize> = (0..n_params)
        .filter(|_| rng.random::<f64>() < inclusion_probability)
        .collect();
    // An empty selection would return the incumbent unchanged and waste an
    // evaluation; the paper mandates perturbing one random dimension instead.
    if selected.is_empty() {
        selected.push(rng.random_range(0..n_params));
    }

    let mut candidate = best.to_owned();
    for &d in &selected {
        let range = upper_bounds[d] - lower_bounds[d];
        let step = r * range * rng.sample::<f64, _>(StandardNormal);
        candidate[d] = reflect_at_bounds(
            best[d] + step,
            lower_bounds[d],
            upper_bounds[d],
        );
    }
    candidate
}

/// Reflect a value at the parameter bounds (Tolson & Shoemaker 2007): an
/// overshoot bounces back inside by the overshot amount; if the bounce
/// crosses the opposite bound, the value is set to the violated bound.
/// Exposed for unit tests.
pub fn reflect_at_bounds(value: f64, lower: f64, upper: f64) -> f64 {
    if value < lower {
        let reflected = lower + (lower - value);
        if reflected > upper {
            lower
        } else {
            reflected
        }
    } else if value > upper {
        let reflected = upper - (value - upper);
        if reflected < lower {
            upper
        } else {
            reflected
        }
    } else {
        value
    }
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "dds")?;
    m.add_class::<Dds>()?;
    Ok(m)
}
