//! Convergence tests on real catchment data: every hydro model, calibrated
//! with both methods (SCE-UA, DDS) and both snow handling modes, must reach a
//! minimum calibration KGE on the Au Saumon and Baskatong catchments.
//!
//! This mirrors the experimental setup of `scripts/run_experiments.py`
//! (objective kge, transformation none, seed 0, 3-year warmup, CemaNeige with
//! fixed parameters [0.25, 3.74, QNBV] in the preprocessing mode).

use std::sync::OnceLock;

use ndarray::{array, s, Array1};

use holmes_rs::calibration::dds::Dds;
use holmes_rs::calibration::sce::Sce;
use holmes_rs::calibration::utils::{Objective, Transformation};

use crate::fixtures;

/// First 10 years of each record: 3-year warmup plus 7 scored years covers
/// several wet/dry cycles and full snow seasons while keeping the 160
/// calibrations tractable inside `make test`.
const WINDOW: usize = 3652;
const WARMUP_STEPS: usize = 1095;

/// Same evaluation budget for both methods so their results are comparable.
/// Half the budget of `run_experiments.py` (5000): enough for every model to
/// clear the conservative floors below. The suite runs outside coverage
/// instrumentation (see the makefile), so this budget costs ~30 s, not
/// minutes. Below ~1000 evaluations SCE degrades sharply (its population
/// alone is 45-105 points), so don't shrink this without re-running the
/// threshold validation survey.
const MAX_EVALUATIONS: usize = 2500;
const SEED: u64 = 0;

/// SCE-UA settings from `run_experiments.py`, with n_complexes reduced
/// 25 -> 5 to fit the smaller evaluation budget.
const N_COMPLEXES: usize = 5;
const K_STOP: usize = 10;
const P_CONVERGENCE_THRESHOLD: f64 = 0.1;
const GEOMETRIC_RANGE_THRESHOLD: f64 = 0.001;

/// DDS neighborhood size, the paper's recommended default.
const DDS_R: f64 = 0.2;

/// Conservative uniform floors on the calibration KGE, validated against a
/// survey run of this exact suite (2026-08-08, budget 2500). Minimum
/// achieved KGE per combination, excluding the wageningen exception in
/// `threshold` (worst model in parentheses):
///
///   Au Saumon  Sce/Preprocessed  0.7453 (nam)
///   Au Saumon  Sce/CoCalibrated  0.7383 (nam)
///   Au Saumon  Dds/Preprocessed  0.8563 (gr4j)
///   Au Saumon  Dds/CoCalibrated  0.8160 (nam)
///   Baskatong  Sce/Preprocessed  0.8634 (tank)
///   Baskatong  Sce/CoCalibrated  0.8428 (tank)
///   Baskatong  Dds/Preprocessed  0.8864 (martine)
///   Baskatong  Dds/CoCalibrated  0.8979 (ihacres)
///
/// Consistent with `data/experiments/experiments.csv` (objective kge,
/// transformation none: >= 0.74 Au Saumon, >= 0.83 Baskatong at a 5000
/// budget). The results are deterministic (fixed seed, budget, and data),
/// so thin margins cannot flake; any config change re-triggers this
/// validation.
const AU_SAUMON_FLOOR: f64 = 0.70;
const BASKATONG_FLOOR: f64 = 0.80;

#[derive(Clone, Copy, Debug)]
enum Catchment {
    AuSaumon,
    Baskatong,
}

#[derive(Clone, Copy, Debug)]
enum Method {
    Sce,
    Dds,
}

#[derive(Clone, Copy, Debug)]
enum SnowMode {
    /// CemaNeige with fixed parameters produces the effective precipitation,
    /// then the hydro model alone is calibrated (as in run_experiments.py).
    Preprocessed,
    /// CemaNeige parameters are calibrated jointly with the hydro model.
    CoCalibrated,
}

macro_rules! convergence_tests {
    ($($model:ident),* $(,)?) => {$(
        mod $model {
            use super::*;

            #[test]
            fn au_saumon_sce_preprocessed() {
                assert_converges(
                    stringify!($model),
                    Catchment::AuSaumon,
                    Method::Sce,
                    SnowMode::Preprocessed,
                );
            }

            #[test]
            fn au_saumon_sce_cocalibrated() {
                assert_converges(
                    stringify!($model),
                    Catchment::AuSaumon,
                    Method::Sce,
                    SnowMode::CoCalibrated,
                );
            }

            #[test]
            fn au_saumon_dds_preprocessed() {
                assert_converges(
                    stringify!($model),
                    Catchment::AuSaumon,
                    Method::Dds,
                    SnowMode::Preprocessed,
                );
            }

            #[test]
            fn au_saumon_dds_cocalibrated() {
                assert_converges(
                    stringify!($model),
                    Catchment::AuSaumon,
                    Method::Dds,
                    SnowMode::CoCalibrated,
                );
            }

            #[test]
            fn baskatong_sce_preprocessed() {
                assert_converges(
                    stringify!($model),
                    Catchment::Baskatong,
                    Method::Sce,
                    SnowMode::Preprocessed,
                );
            }

            #[test]
            fn baskatong_sce_cocalibrated() {
                assert_converges(
                    stringify!($model),
                    Catchment::Baskatong,
                    Method::Sce,
                    SnowMode::CoCalibrated,
                );
            }

            #[test]
            fn baskatong_dds_preprocessed() {
                assert_converges(
                    stringify!($model),
                    Catchment::Baskatong,
                    Method::Dds,
                    SnowMode::Preprocessed,
                );
            }

            #[test]
            fn baskatong_dds_cocalibrated() {
                assert_converges(
                    stringify!($model),
                    Catchment::Baskatong,
                    Method::Dds,
                    SnowMode::CoCalibrated,
                );
            }
        }
    )*};
}

convergence_tests!(
    bucket, cequeau, crec, gardenia, gr4j, hbv, hymod, ihacres, martine,
    mohyse, mordor, nam, pdm, sacramento, simhyd, smar, tank, topmodel,
    wageningen, xinanjiang,
);

fn assert_converges(
    model: &str,
    catchment: Catchment,
    method: Method,
    snow: SnowMode,
) {
    let kge = run_calibration(model, catchment, method, snow);
    let floor = threshold(model, catchment);
    // Visible with `cargo test --test performance -- --nocapture`; used to
    // audit achieved values when revisiting the floors.
    println!("PERF {model} {catchment:?} {method:?} {snow:?} kge={kge:.4}");
    assert!(
        kge >= floor,
        "{model} on {catchment:?} ({method:?}, {snow:?}) reached calibration \
         KGE {kge:.4}, below the floor {floor}"
    );
}

fn threshold(model: &str, catchment: Catchment) -> f64 {
    match (model, catchment) {
        // wageningen underperforms the other models on Au Saumon with SCE
        // (0.6738 preprocessed vs >= 0.7383 for everyone else in the survey
        // run). Investigated against the primary sources: the port matches
        // HOOPLA HydroMod19.m line for line, which itself matches the
        // retained WAGE structure of Perrin (2000), fiche 34 §18 — no
        // transcription bug (see docs/concepts/hydro/wageningen.md). The
        // structure is erratic on Au Saumon (Seiller et al. 2012, HESS 16:
        // best model of one climate-transfer test, worst of another) and its
        // objective surface traps SCE in a local optimum: on this exact
        // window and bounds, DDS reaches KGE 0.88 where SCE stalls at 0.67.
        // The 0.60 floor is a regression tripwire for that worst (SCE) case.
        ("wageningen", Catchment::AuSaumon) => 0.60,
        (_, Catchment::AuSaumon) => AU_SAUMON_FLOOR,
        (_, Catchment::Baskatong) => BASKATONG_FLOOR,
    }
}

fn run_calibration(
    model: &str,
    catchment: Catchment,
    method: Method,
    snow: SnowMode,
) -> f64 {
    let prepared = prepared(catchment);

    let (precipitation, snow_model) = match snow {
        SnowMode::Preprocessed => {
            (prepared.effective_precipitation.view(), None)
        }
        SnowMode::CoCalibrated => {
            (prepared.data.precipitation.view(), Some("cemaneige"))
        }
    };
    let (temperature, day_of_year, elevation_bands, median_elevation) =
        match snow {
            SnowMode::Preprocessed => (None, None, None, None),
            SnowMode::CoCalibrated => (
                Some(prepared.data.temperature.view()),
                Some(prepared.data.day_of_year.view()),
                Some(prepared.info.elevation_bands.view()),
                Some(prepared.info.median_elevation),
            ),
        };
    let pet = prepared.data.pet.view();
    let observations = prepared.data.observed_flow.view();

    // Both optimizers stop on their own termination criteria; the explicit
    // iteration cap only guards against a runaway loop if that ever breaks.
    const MAX_STEPS: usize = 10 * MAX_EVALUATIONS;

    match method {
        Method::Sce => {
            let mut sce = Sce::new(
                model,
                snow_model,
                Objective::Kge,
                Transformation::None,
                N_COMPLEXES,
                K_STOP,
                P_CONVERGENCE_THRESHOLD,
                GEOMETRIC_RANGE_THRESHOLD,
                MAX_EVALUATIONS,
                SEED,
            )
            .expect("valid model names and SCE settings");
            sce.init(
                precipitation,
                temperature,
                pet,
                day_of_year,
                elevation_bands,
                median_elevation,
                observations,
                WARMUP_STEPS,
            )
            .expect("init succeeds on real fixture data");
            for _ in 0..MAX_STEPS {
                let (done, _, _, objectives) = sce
                    .step(
                        precipitation,
                        temperature,
                        pet,
                        day_of_year,
                        elevation_bands,
                        median_elevation,
                        observations,
                        WARMUP_STEPS,
                    )
                    .expect("step succeeds on real fixture data");
                if done {
                    return objectives[2];
                }
            }
        }
        Method::Dds => {
            let mut dds = Dds::new(
                model,
                snow_model,
                Objective::Kge,
                Transformation::None,
                DDS_R,
                MAX_EVALUATIONS,
                SEED,
            )
            .expect("valid model names and DDS settings");
            dds.init(
                precipitation,
                temperature,
                pet,
                day_of_year,
                elevation_bands,
                median_elevation,
                observations,
                WARMUP_STEPS,
            )
            .expect("init succeeds on real fixture data");
            for _ in 0..MAX_STEPS {
                let (done, _, _, objectives) = dds
                    .step(
                        precipitation,
                        temperature,
                        pet,
                        day_of_year,
                        elevation_bands,
                        median_elevation,
                        observations,
                        WARMUP_STEPS,
                    )
                    .expect("step succeeds on real fixture data");
                if done {
                    return objectives[2];
                }
            }
        }
    }
    panic!(
        "{model} calibration did not terminate within {MAX_STEPS} steps \
         ({method:?}, {snow:?})"
    );
}

struct PreparedCatchment {
    data: fixtures::CatchmentData,
    info: fixtures::CemaNeigeInfo,
    /// CemaNeige output with the fixed parameters used by
    /// run_experiments.py: [0.25, 3.74, QNBV].
    effective_precipitation: Array1<f64>,
}

/// Load, slice, and preprocess each catchment exactly once per test binary.
fn prepared(catchment: Catchment) -> &'static PreparedCatchment {
    static AU_SAUMON: OnceLock<PreparedCatchment> = OnceLock::new();
    static BASKATONG: OnceLock<PreparedCatchment> = OnceLock::new();

    let (cell, observations_file, info_file) = match catchment {
        Catchment::AuSaumon => (
            &AU_SAUMON,
            "observations_au_saumon.csv",
            "cemaneige_info_au_saumon.csv",
        ),
        Catchment::Baskatong => (
            &BASKATONG,
            "observations_baskatong.csv",
            "cemaneige_info_baskatong.csv",
        ),
    };
    cell.get_or_init(|| prepare(observations_file, info_file))
}

fn prepare(observations_file: &str, info_file: &str) -> PreparedCatchment {
    let raw = fixtures::load_catchment_data(
        &fixtures::fixtures_dir().join(observations_file),
    )
    .expect("catchment observations fixture loads");
    assert!(
        raw.precipitation.len() >= WINDOW,
        "{observations_file} is shorter than the {WINDOW}-step test window"
    );

    let data = fixtures::CatchmentData {
        precipitation: raw.precipitation.slice(s![..WINDOW]).to_owned(),
        temperature: raw.temperature.slice(s![..WINDOW]).to_owned(),
        pet: raw.pet.slice(s![..WINDOW]).to_owned(),
        observed_flow: raw.observed_flow.slice(s![..WINDOW]).to_owned(),
        day_of_year: raw.day_of_year.slice(s![..WINDOW]).to_owned(),
    };
    let info = fixtures::load_cemaneige_info(
        &fixtures::fixtures_dir().join(info_file),
    )
    .expect("cemaneige info fixture loads");

    let snow_params = array![0.25, 3.74, info.qnbv];
    let effective_precipitation = holmes_rs::snow::cemaneige::simulate(
        snow_params.view(),
        data.precipitation.view(),
        data.temperature.view(),
        data.day_of_year.view(),
        info.elevation_bands.view(),
        info.median_elevation,
    )
    .expect("cemaneige preprocessing succeeds on real fixture data");

    PreparedCatchment {
        data,
        info,
        effective_precipitation,
    }
}
