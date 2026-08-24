---
name: add-hydro-model
description: Add a new hydrological model to HOLMES end-to-end — Rust implementation, PyO3 bindings, Python registry, type stubs, tests at three levels, changelogs, and MkDocs concept page + nav wiring. Invoke with `/add-hydro-model`; the skill prompts for the model name. Uses `hoopla-models.md` as a lookup table and `perrin/these_annexe.pdf` + HOOPLA Matlab source as equation references.
---

# Add a Hydrological Model

End-to-end workflow for plugging a new hydrological model into HOLMES.
The skill touches **12 files** across the Rust crate, the Python wrapper, both test suites, the two changelogs, and the MkDocs concept docs.
Frontend and API require no edits — backend model discovery is automatic via `get_args(HydroModel)`.
The docs sidebar is also automatic: `docs/concepts/hydro/` is driven by the `awesome-nav` plugin with a `"*"` glob, so dropping a new concept page into that directory wires it into the nav with zero config edits. The only manual docs edit is adding one row to the comparison table in `docs/concepts/index.md`.

## Usage

Invoke with `/add-hydro-model` (no arguments).
The skill then:

1. Reads `.claude/skills/add-hydro-model/hoopla-models.md` and presents the "To implement" rows via `AskUserQuestion` so the user picks from a concrete shortlist.
2. Fetches the selected model's equations from HOOPLA Matlab source and cross-checks against Perrin's thesis annex.
3. Walks through the 12-file checklist, building and testing after each major phase.
4. Copies `.claude/skills/add-hydro-model/_template.md` into `docs/concepts/hydro/<name>.md` and fills in the six required sections, then appends one row to the comparison table in `docs/concepts/index.md`.
5. Stops before committing — all files are left modified so the user can inspect the full diff and commit themselves.

## References to consult (in order)

1. **`.claude/skills/add-hydro-model/hoopla-models.md`** — **start here.** Static lookup table: for any HOOPLA model, gives the HM folder number, expected parameter count, and the two raw-URL links to its Matlab source (`ini_HydroModN.m` + `HydroModN.m`). Also shows which models are already implemented.
2. **`perrin/these_annexe.pdf`** — Perrin's thesis annex, Annexe 1 "Description des modèles" (starts around page 291). Primary source for equations, parameter bounds, and initial reservoir states. Read with the `Read` tool using a `pages:` range — the PDF is 246 pages so a range is required.
3. **HOOPLA Matlab source** — `WebFetch` both raw URLs from `hoopla-models.md` to cross-check equations and parameter ordering when Perrin's notation is ambiguous. The step file (`HydroModN.m`) contains the human-readable name and the production/routing equations; the init file (`ini_HydroModN.m`) contains the reservoir state defaults and unit-hydrograph setup.
4. **`src/holmes-rs/src/hydro/gardenia.rs`** — newest Rust implementation. Use as primary template. Shows the full `param_names` + `BOUNDS` + `init()` + `simulate()` + `py_init` + `py_simulate` + `make_module` pattern.
5. **`src/holmes-rs/src/hydro/gr4j.rs`** — secondary reference for the unit-hydrograph / delay-routing pattern (if the new model needs one).
6. **`src/holmes-rs/src/hydro/utils.rs`** — `HydroError` variants and validation helpers (`validate_parameter`, `check_lengths`, `validate_inputs_finite`, `validate_non_negative`, `validate_output`) that every `simulate()` must use.
7. **`.claude/skills/add-hydro-model/_template.md`** — canonical template for the docs concept page, with the six-section schema pre-filled as empty stubs and inline HTML comments documenting the writing rules. Copy it verbatim into `docs/concepts/hydro/<name>.md` and replace the placeholders. For concrete worked examples (especially when the new model has unusual structure), cross-reference the five existing pages in `docs/concepts/hydro/`:
   - **`gr4j.md`** — unit hydrograph + nonlinear routing store + groundwater exchange.
   - **`bucket.md`** — linear reservoir cascade, simplest structure.
   - **`cequeau.md`** — two-reservoir model with threshold-based and continuous drainage pathways.
   - **`crec.md`** — sigmoid rainfall-splitting function.
   - **`hymod.md`** — Pareto-distributed soil store.

## Architecture primer

Every hydrological model in HOLMES must expose exactly four public symbols from its Rust module:

- `pub const param_names: &[&str]` — e.g. `&["x1", "x2", "x3", "x4"]`.
- `pub const param_descriptions: &[&str]` — one human-readable description per parameter.
- `pub fn init() -> (Array1<f64>, Array2<f64>)` — returns `(default_values, bounds_matrix)` where `bounds_matrix` is shape `(n_params, 2)` with `[lower, upper]` in each row.
- `pub fn simulate(params: ArrayView1<f64>, precipitation: ArrayView1<f64>, pet: ArrayView1<f64>) -> Result<Array1<f64>, HydroError>` — full-series simulation, one streamflow value per time step.

The Python layer (`src/holmes/model.py`) uses a `Literal` type for dispatch, and the calibration / WebSocket API / frontend all auto-discover new models via `get_args(model.HydroModel)` — so adding a new model requires **zero** frontend or API changes. `src/holmes/model_info.py` additionally carries a per-model display name + `param_descriptions` entry (`_get_hydro_model_info`).

## The 12-file checklist

Based on the GARDENIA reference commit `e556f1c` (which covered files 1–11 of the pre-automod numbering) plus the documentation touchpoints (now files 11–12) — GARDENIA itself shipped without docs and should be backfilled when convenient. The old file #6 edit (`tests/unit/hydro/mod.rs`) is obsolete since `automod::dir!` auto-discovers every `*_tests.rs` file in the directory at compile time. `<name>` is the lowercase model identifier (e.g. `hymod`, `hbv`, `ihacres`); `<Name>` is PascalCase for Python test classes and the docs page title; `<NAME>` is uppercase for changelog entries.

| # | File | Type | What to do |
|---|------|------|------------|
| 1 | `src/holmes-rs/src/hydro/<name>.rs` | new | Implement `param_names`, `param_descriptions`, `BOUNDS`, `init`, `simulate`, `py_init`, `py_simulate`, `make_module`. Template: `gardenia.rs`. |
| 2 | `src/holmes-rs/src/hydro/mod.rs` | edit | Add `pub mod <name>;`. Add `register_submodule(py, &m, &<name>::make_module(py)?, "holmes_rs.hydro")?;` inside `make_module`. Add `"<name>" => Ok((<name>::init, <name>::simulate)),` inside `get_model`. |
| 3 | `src/holmes-rs/python/holmes_rs/hydro/<name>.pyi` | new | Type stub declaring module-level `param_names: list[str]`, `param_descriptions: list[str]`, and signatures for `init()` and `simulate()`. Template: `gardenia.pyi`. |
| 4 | `src/holmes-rs/python/holmes_rs/hydro/__init__.pyi` | edit | Add `<name>` to the `from . import ...` line. |
| 5 | `src/holmes-rs/tests/unit/hydro/<name>_tests.rs` | new | Rust unit tests — init shape/bounds, simulate happy path, zero precipitation, parameter-count mismatch, length mismatch, bounds violations, NaN/negative input, proptest block. Target ≥99% Rust coverage. Template: `gardenia_tests.rs`. **No `mod.rs` edit is required** — `tests/unit/hydro/mod.rs` uses `automod::dir!` to auto-discover every `*_tests.rs` sibling at compile time. |
| 6 | `src/holmes-rs/tests/python_integration/test_hydro.py` | edit | Add `Test<Name>Init`, `Test<Name>Simulate`, `Test<Name>ParamNames`, `Test<Name>ParamDescriptions` classes. |
| 7 | `src/holmes/model.py` + `src/holmes/model_info.py` | edit | In `model.py`: add `"<name>"` to `HydroModel = Literal[...]` and a case in the `_get_hydro_model` match (and `get_config` if it dispatches per model). In `model_info.py`: add a `case "<name>":` in `_get_hydro_model_info` with the display name and `holmes_rs.hydro.<name>.param_descriptions`. |
| 8 | `tests/unit/test_model.py` + `tests/unit/test_model_info.py` | edit | Add tests for the new dispatch cases (`get_config` / `_get_hydro_model`), the model-info entry, and error propagation for `HolmesNumericalError` / `HolmesValidationError`. |
| 9 | `src/holmes-rs/CHANGELOG.md` | edit | Under `[Unreleased]` → `Added`: `- Add <NAME> hydrological model (N parameters)`. |
| 10 | `CHANGELOG.md` | edit | Under `[Unreleased]` → `Added`: same entry. |
| 11 | `docs/concepts/hydro/<name>.md` | new | New concept page. **Copy `.claude/skills/add-hydro-model/_template.md` verbatim** and replace the placeholders. The six-section schema is mandatory: `## Overview`, `## Key Concepts`, `## How It Works`, `## Parameters` (Markdown table), `## Mathematical Formulation`, `## References`. Use MathJax (`$...$` inline, `$$...$$` block) and student-level prose — this is course material, not API reference. `awesome-nav` picks the page up automatically via the `"*"` glob in `docs/concepts/hydro/.nav.yml`, so **no sidebar or mkdocs.yml edit is needed**. |
| 12 | `docs/concepts/index.md` | edit | Three edits, all small: (a) add one bullet describing the new model under `### 3. Hydrological Transformation`, (b) append one row to the "Choosing the Right Model" model-as-row table — keep column order intact: **Model \| Params \| Soil store \| Flow partitioning \| Routing \| GW exchange \| Equifinality \| Best for** — and keep rows in alphabetical order to match the sidebar, (c) add one link under `## Further Reading`. |

## Rust implementation skeleton

Drop-in template for file 1. Replace `newmodel` with the lowercase name and fill in the production/routing equations from Perrin + HOOPLA.

```rust
use ndarray::{array, Array1, Array2, ArrayView1, Axis, Zip};
use numpy::{PyArray1, PyArray2, PyReadonlyArray1, ToPyArray};
use pyo3::prelude::*;

use crate::hydro::utils::{
    check_lengths, validate_inputs_finite, validate_non_negative, validate_output,
    validate_parameter, HydroError,
};

pub const param_names: &[&str] = &["x1", "x2", "x3", "x4"];
pub const param_descriptions: &[&str] = &[
    "Short description of x1 (units)",
    "Short description of x2 (units)",
    "Short description of x3 (units)",
    "Short description of x4 (units)",
];

const BOUNDS: [(&str, f64, f64); 4] = [
    ("x1", 1.0, 1000.0),
    ("x2", 0.01, 10.0),
    ("x3", 1.0, 500.0),
    ("x4", 0.5, 10.0),
];

pub fn init() -> (Array1<f64>, Array2<f64>) {
    let bounds = array![
        [BOUNDS[0].1, BOUNDS[0].2],
        [BOUNDS[1].1, BOUNDS[1].2],
        [BOUNDS[2].1, BOUNDS[2].2],
        [BOUNDS[3].1, BOUNDS[3].2],
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

    for (i, &v) in [x1, x2, x3, x4].iter().enumerate() {
        let (name, lower, upper) = BOUNDS[i];
        validate_parameter(v, name, lower, upper)?;
    }

    check_lengths(precipitation, pet)?;
    validate_inputs_finite(precipitation, "precipitation")?;
    validate_inputs_finite(pet, "pet")?;
    validate_non_negative(precipitation, "precipitation")?;
    validate_non_negative(pet, "pet")?;

    let mut streamflow: Vec<f64> = vec![0.0; precipitation.len()];

    // TODO: replace with actual reservoir states from Perrin annex / HOOPLA
    let mut s: f64 = x1 * 0.5;
    let mut r: f64 = 10.0;

    Zip::indexed(&precipitation).and(&pet).for_each(|t, &p, &e| {
        // TODO: production phase — soil moisture accounting
        // TODO: routing phase — flow transfer
        // Write result for this time step:
        streamflow[t] = 0.0; // replace
        let _ = (p, e, &mut s, &mut r, x1, x2, x3, x4);
    });

    let result = Array1::from_vec(streamflow);
    validate_output(result.view(), "NEWMODEL simulation")?;
    Ok(result)
}

#[cfg_attr(coverage_nightly, coverage(off))]
#[pyfunction]
#[pyo3(name = "init")]
pub fn py_init<'py>(py: Python<'py>) -> (Bound<'py, PyArray1<f64>>, Bound<'py, PyArray2<f64>>) {
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
    let simulation = simulate(params.as_array(), precipitation.as_array(), pet.as_array())?;
    Ok(simulation.to_pyarray(py))
}

#[cfg_attr(coverage_nightly, coverage(off))]
pub fn make_module(py: Python<'_>) -> PyResult<Bound<'_, PyModule>> {
    let m = PyModule::new(py, "newmodel")?;
    m.add("param_names", param_names)?;
    m.add("param_descriptions", param_descriptions)?;
    m.add_function(wrap_pyfunction!(py_init, &m)?)?;
    m.add_function(wrap_pyfunction!(py_simulate, &m)?)?;
    Ok(m)
}
```

## Workflow

1. **Pick the model.** Read `.claude/skills/add-hydro-model/hoopla-models.md`, extract the "To implement" rows, and present them via `AskUserQuestion` so the user selects one. Record the HM number, expected parameter count, and the two raw URLs.
2. **Study the equations.** `Read` `perrin/these_annexe.pdf` with a `pages:` range covering the target model in Annexe 1 (~page 291 onward). Then `WebFetch` both HOOPLA raw URLs to cross-check parameter ordering, reservoir initialization, and edge-case handling. Build a mental model of: production phase, routing phase, reservoir states, unit hydrograph (if any), parameter bounds.
3. **Write file 1** (`src/holmes-rs/src/hydro/<name>.rs`) using the skeleton above. Fill in `BOUNDS` from Perrin/HOOPLA. Implement the time-step loop.
4. **Wire in file 2** (`src/holmes-rs/src/hydro/mod.rs`). Build to catch compile errors early:
   ```
   cd src/holmes-rs && maturin develop --release
   ```
5. **Add type stubs** (files 3 and 4).
6. **Write Rust unit tests** (file 5) following `gardenia_tests.rs`. No `mod.rs` edit is needed — `tests/unit/hydro/mod.rs` uses `automod::dir!` and picks up the new file automatically. Run until green:
   ```
   cd src/holmes-rs && cargo test <name>
   ```
7. **Check Rust coverage.** Add tests until lines ≥ 99 %:
   ```
   cd src/holmes-rs && cargo +nightly llvm-cov --html
   ```
8. **Write Python-integration tests** (file 6) and run:
   ```
   cd src/holmes-rs && pytest tests/python_integration -k <name>
   ```
9. **Wire the Python registry** (file 7). Then write Python-layer tests (file 8) and run:
   ```
   pytest tests/unit/test_model.py tests/unit/test_model_info.py -k <name>
   ```
10. **Full quality gate.** Fix any regressions:
    ```
    make static-analysis
    make test
    ```
11. **Update both changelogs** (files 9 and 10).
12. **Run the full-data smoke test.** This is **mandatory**, not optional — it is the only step that catches implementation bugs that unit tests miss (e.g. a sign error in a routing equation that still produces finite, non-negative streamflow but gives nonsense KGE on real data):
    ```
    holmes experiment
    ```
    The `hydro_model="all"` experiments in `src/holmes/experiment.py` fan out over every `HydroModel` (including the new one, via `get_args`), calibrating and simulating on real station data. Results are content-addressed under `data/results/experiments/<hash>/results.csv` with a registry in `data/results/experiments/experiments.json`; every stage is skip-if-cached, so re-runs are cheap.

13. **Compare the new model's KGE to the existing models.** Locate the `hydro_model="all"` runs via `experiments.json`, load their `results.csv` files with Polars, and compare the new model's KGE per station against the median across the already-implemented models.
    Sanity criteria — all must hold, otherwise investigate before declaring done:
    - **No NaN or infinite KGE** for the new model on any catchment.
    - **Median gap ≥ −0.20** (new model within 0.2 KGE of the others-average on the typical station). A systematic −0.3 or worse on every station almost certainly means a bug in the production or routing equations.
    - **At least one station where `kge ≥ 0.5`**. A model that can never reach 0.5 is either broken or has bounds set wrong; recheck `BOUNDS` against Perrin's annex.
    - **Bottom-quartile stations are plausible failure cases** — some models legitimately struggle on snow-dominated or karstic watersheds, so a localized poor fit is acceptable if the others also struggle there.

14. **Write the docs concept page** (file 11). Copy `.claude/skills/add-hydro-model/_template.md` into `docs/concepts/hydro/<name>.md` and replace the placeholders. The template's inline HTML comments document the six-section schema and the writing rules. Pull equations from Perrin's thesis annex (notation should match what a student reads there, e.g. `X_1`, `S`, `R` — **not** HOOPLA Matlab names like `HM16_x(1)`); use the parameter bounds from `BOUNDS` in step 3 as the authoritative source for the Range column. `awesome-nav` will discover the new page automatically via the `"*"` glob in `docs/concepts/hydro/.nav.yml` — no sidebar or `mkdocs.yml` edit is needed.

15. **Update the concepts intro** (file 12). Three small edits to `docs/concepts/index.md`:
    - Add one bullet under `### 3. Hydrological Transformation` describing the new model in one sentence.
    - Append one row to the "Choosing the Right Model" model-as-row comparison table. Column order: **Model (linked) \| Params \| Soil store \| Flow partitioning \| Routing \| GW exchange \| Equifinality \| Best for**. Keep rows in alphabetical order by model name so they match the sidebar ordering.
    - Add one link under `## Further Reading`, also in alphabetical order.

16. **Preview the docs** to catch MathJax typos and visual regressions. The nav is driven by `awesome-nav` so broken links to the new page are unlikely, but equation rendering and table layout still need eyeballs:
    ```
    mkdocs build --strict
    ```
    No warnings should appear. Then run `mkdocs serve` and spot-check the rendered page.

17. **Update the lookup table.** In `.claude/skills/add-hydro-model/hoopla-models.md`, change the model's status from "To implement" to "Implemented".

18. **Do not commit.** Report `git status`, a brief `git diff --stat` of the Rust + Python + docs files, and the comparison table from step 13. Let the user inspect and commit.

## Verification checklist

Done means **all** of the following:

- `make static-analysis` passes (ruff, ty, cargo fmt, clippy).
- `make test` passes.
- `pytest tests/unit tests/integration --cov=src/holmes --cov-report=term-missing` shows 100 % coverage for the `holmes` package (unit + integration combined — the coverage gate spans both).
- `cd src/holmes-rs && cargo +nightly llvm-cov` shows ≥ 99 % Rust line coverage.
- The new model appears in `get_args(holmes.model.HydroModel)`.
- `python -c "from holmes.model import get_config; print(get_config('<name>'))"` prints the parameter config with names, defaults, bounds.
- The frontend dropdown lists the new model (start `holmes run` and visually confirm — the dropdown is populated from the backend `model_info` message, no JS change needed).
- `holmes experiment` has been run at least once with the new model included, adding results under `data/results/experiments/`.
- The Polars comparison from step 13 passes all four sanity criteria: no NaN/inf KGE, median gap ≥ −0.20 vs other models, at least one station with KGE ≥ 0.5, and any weak stations are legitimately hard (not a systematic failure).
- `docs/concepts/hydro/<name>.md` exists and follows the six-section schema from `.claude/skills/add-hydro-model/_template.md`.
- `docs/concepts/index.md` mentions the new model in the transformation bullets, the comparison table (as a new alphabetically-sorted row), and the further-reading list.
- `mkdocs build --strict` passes with no warnings.
- `mkdocs serve` renders the new page, all MathJax blocks display, and the sidebar shows the new page under **Concepts → Hydrological models** (awesome-nav auto-discovery).
- `hoopla-models.md` status for this model is now "Implemented".
- No git commits created by the skill (`git status` shows uncommitted changes).

## Common pitfalls

- **Forgetting to extend `HydroModel = Literal[...]`** → `assert_never` fires at runtime in the match arms, and `get_args` never advertises the model to the frontend.
- **Missing `validate_output(result.view(), ...)`** at the end of `simulate` → NaN leaks into calibration and SCE-UA explodes with opaque errors.
- **Wrong parameter count in `ParamsMismatch(expected, got)`** → must match `param_names.len()`. Destructure with `let [x1, x2, ...]: [f64; N] = ...`.
- **Division-by-zero branches in the time-step loop** — e.g. `r * r / (r + x2 * x3)` is only safe if bounds prevent the denominator from reaching zero. Add a proptest that exercises the bound corners.
- **Missing `#[cfg_attr(coverage_nightly, coverage(off))]`** on PyO3 wrapper functions → coverage target drops below 99 % threshold because PyO3 glue is untestable from Rust side.
- **Lowercase model identifier mismatch** between the Python `Literal`, the Rust `get_model` match arm, and the `make_module` name → runtime dispatch fails silently.
- **HOOPLA header typos on parameter counts** — HM18 (TOPMODEL) and HM19 (WAGENINGEN) have prose/array disagreement in their headers. Trust the array dimension (`[7,1]` or `[8,1]`), not the free-text word. See `hoopla-models.md` footnotes.
- **Docs page written outside `docs/concepts/hydro/`** → `awesome-nav`'s `"*"` glob only matches files in that directory. If the page is placed at `docs/concepts/<name>.md` (old flat layout) it will build but never appear in the sidebar. Always put new hydro concept pages under `docs/concepts/hydro/`.
- **Intro page (`concepts/index.md`) out of sync with the sidebar** — the comparison table, the transformation bullets, and the Further Reading list are still hand-maintained. `awesome-nav` handles the sidebar automatically, so the most likely symptom of forgetting file 12 is a student landing on `Concepts` and seeing a model listed in the sidebar that doesn't appear in the comparison table.
- **Comparison table rows out of alphabetical order** — rows must match the alphabetical order `awesome-nav` uses for the sidebar, otherwise `Bucket → CEQUEAU → CREC → GR4J → HYMOD` in the sidebar doesn't match the table order and the student has to mentally re-sort to cross-reference.
- **Copying equation notation from HOOPLA Matlab source instead of Perrin's thesis annex** — HOOPLA variable names (`HM16_x(1)`, etc.) are not student-friendly. The docs page is course material, so the notation should match what students read in Perrin's annex (`X_1`, `X_2`, `S`, `R`, etc.). Use HOOPLA only as a disambiguation check, not as the source of typeset equations.
- **Editing `mkdocs.yml`'s missing `nav` block** — `mkdocs.yml` no longer has a `nav:` section; the nav lives in `docs/.nav.yml` and `docs/concepts/.nav.yml`. New hydro models don't need any nav edits at all because `docs/concepts/hydro/.nav.yml` is just `nav: ["*"]`. Don't try to "restore" the old nav block — it was deleted intentionally when the awesome-nav plugin was adopted.
