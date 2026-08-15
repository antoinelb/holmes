# Changelog

All notable changes to the holmes Python package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For changes to the Rust extension, see [src/holmes-rs/CHANGELOG.md](src/holmes-rs/CHANGELOG.md).

<!-- changelog-start -->

## [Unreleased]

### Added
- `holmes package` command zipping every built data product into the dated `data-YYYY-MM-DD.zip` archive published on the repo's rolling `data` release
- Nightly data-refresh GitHub Actions workflow (`.github/workflows/data.yml`) running `holmes download` and `holmes package` and replacing the dated archive on the `data` release, toggled with the `DATA_REFRESH_ENABLED` repository variable (manual runs always allowed)
- `HOLMES_SKIP_DATA_SYNC` environment variable to skip the startup data sync

### Changed
- **Breaking**: the server no longer builds data at runtime: every product is pre-built and served as one dated zip on the `data` release; at startup the server downloads and extracts a newer archive if one exists (keeping the current data served during the swap) and raises an actionable `MissingDataError` when no data is available at all — map tiles remain the one lazily fetched exception
- **Breaking**: data now lives in the per-user data directory (`~/.local/share/holmes` on Linux, `~/Library/Application Support/holmes` on macOS, `%LOCALAPPDATA%\holmes\holmes` on Windows) instead of the working directory's `data/`, overridable with the `HOLMES_DATA_DIR` environment variable (a repo checkout uses `HOLMES_DATA_DIR=data`)
- **Breaking**: `holmes download` is now the maintainer path building every product incrementally from its true source — daily re-runs only fetch the current year (plus the previous year in January) for ERA5 and the ministry grid, always refresh the streamflow files, recompute the cheap derived products, and skip the static ones — and requires the new `download` optional extra (`pip install 'holmes-hydro[download]'`), which carries the heavy geo dependencies (cdsapi, xarray, rioxarray, exactextract, netcdf4, pystac-client) removed from the base install

### Removed
- **Breaking**: the runtime cache-or-fetch data layer, the committed data files fetched from the repo, and the per-product release assets, all superseded by the dated archive on the `data` release

## [4.2.1] - 2026-08-15

### Fixed
- Installation no longer fails with uv or pip ≥ 24.1: the abandoned pre-release `geopolars` dependency (invalid metadata rejected by modern pip) was replaced with the already-required `geopandas`, also dropping the transitive `pyarrow` dependency

## [4.2.0] - 2026-08-15

### Added
- Running `holmes` without a subcommand now starts the dashboard, equivalent to `holmes run`

## [4.1.0] - 2026-08-08

### Added
- User guide in the documentation covering every step and feature of the application, with screenshots in both themes (regenerated with `make screenshots`)
- The application is now bilingual (English/French): a language button in the settings menu (hotkey L) switches every label, chart legend, dialog and model description; the choice persists in localStorage and defaults to English
- Model and parameter descriptions are served in both languages (`model_info`/`calibration_info` payloads carry `{en, fr}` texts backed by `param_descriptions_fr` in holmes-rs 0.7.0)
- The documentation is bilingual too (`mkdocs-static-i18n`): every page has a French sibling, a language switcher on every page, and French-UI screenshot pairs (`<scene>-fr-{dark,light}.png`) captured by the same `make screenshots` walk

### Changed
- Chart time axes use French month names when the language is French
- Documentation no longer uses Material's `navigation.instant`, which is incompatible with the language switcher's contextual links

## [4.0.0] - 2026-08-08

### Changed
- **Breaking**: complete rewrite of the application.
  The UI is now a guided pipeline (stations → weather → model → calibration → simulation → projection) built on an Elm-architecture vanilla-JS frontend with an interactive Leaflet station map, replacing the tabbed catchment interface
- **Breaking**: the data model is station-based — hydrometric stations (DEH) with weather built from ERA5, nearest MELCC stations, or the ministry grid, replacing the shipped per-catchment CSV bundles; data is fetched from its true source at runtime and cached under `data/`
- **Breaking**: the CLI is now a Typer app with subcommands: `holmes run` (dashboard), `holmes download` (rebuild the published datasets), and `holmes experiment` (run batch experiments); the entry point moved from `holmes.app:run_server` to `holmes.cli:run_cli`
- **Breaking**: minimum supported Python is now 3.12
- Climate projections are fetched per station from PAVICS (ClimEx and ESPO-G6-R2), with prebuilt products served from the repo's `data` release instead of shipped projection CSV files

### Removed
- **Breaking**: shipped catchment datasets and the observations / CemaNeige-info / projections CSV input formats
- `scripts/download_hydro_data.py`, `scripts/run_experiments.py`, and `scripts/convert_projections_format.py`, superseded by `holmes download` and `holmes experiment`

## [3.5.0] - 2026-04-29

### Added
- WAGENINGEN hydrological model (8-parameter HOOPLA HM19 port of the Warmerdam et al. 1997 model with threshold-based soil-moisture production, capillary rise, cosine ET envelope, fast/slow flow dissociation via the `x5` threshold, and fractional-delay routing) support in model registry, config, and simulation dispatching
- TANK hydrological model (7-parameter Perrin variant of the Sugawara 1979 cascade of four linear reservoirs S→R→T→L with dual-threshold side-outlets on the surface store, geometric drain-time scaling, cascading ET satisfaction, and fractional-delay routing) support in model registry, config, and simulation dispatching
- MORDOR hydrological model (6-parameter Garçon 1999 formulation with four cascading reservoirs U→L→Z→N, proportional rainfall partitioning, nonlinear cubic groundwater discharge, and three-component double-sided UH2 routing with exponent 2.5) support in model registry, config, and simulation dispatching
- MARTINE hydrological model (7-parameter Perrin variant of the Mazenc et al. 1984 BRGM model with overflow production, quadratic direct routing, dual-pathway intermediate reservoir, and linear groundwater recession) support in model registry, config, and simulation dispatching
- CREC hydrological model support in model registry, config, and simulation dispatching
- CREC model documentation page with mathematical formulation, 6-parameter description, and model comparison table update
- GARDENIA hydrological model support in model registry, config, and simulation dispatching
- HYMOD hydrological model support in model registry, config, and simulation dispatching
- HBV hydrological model (9-parameter Bergström/Forsman HBV0 variant) support in model registry, config, and simulation dispatching
- XINANJIANG hydrological model (8-parameter Perrin variant of the Zhao et al. 1980 saturation-excess model) support in model registry, config, and simulation dispatching
- SACRAMENTO hydrological model (9-parameter Perrin variant of the Burnash et al. 1973 NWSRFS model) support in model registry, config, and simulation dispatching
- IHACRES hydrological model (7-parameter Perrin variant of the Jakeman et al. 1990 model with PET-modulated drying constant and parallel fast/slow linear routing) support in model registry, config, and simulation dispatching
- TOPMODEL hydrological model (7-parameter Perrin variant of the Beven & Kirkby 1979 model with sigmoid recharge/ET partitioning, exponential groundwater store, and quadratic surface routing) support in model registry, config, and simulation dispatching
- NAM hydrological model (10-parameter HOOPLA HM12 port of the Nielsen & Hansen 1973 Nedbør-Afstrømnings-Model with seven reservoirs and a fractional-delay unit hydrograph) support in model registry, config, and simulation dispatching
- PDM hydrological model (8-parameter HOOPLA HM13 port of the Moore & Clarke 1981 Probability-Distributed Model with Pareto soil store, cubic ground reservoir, two-stage linear cascade, and fractional-delay routing) support in model registry, config, and simulation dispatching
- MOHYSE hydrological model (7-parameter HOOPLA HM10 port of the Fortin & Turcotte 2007 MOdèle HYdrologique Simplifié à l'Extrême with capacity-limited infiltration, dual soil/groundwater linear reservoirs, and gamma unit hydrograph routing) support in model registry, config, and simulation dispatching
- SMAR hydrological model (8-parameter Perrin variant of the O'Connell et al. 1970 Soil Moisture Accounting and Routing model with 16-layer soil column, exponentially decaying ET, dual linear/quadratic routing, and fractional-delay routing) support in model registry, config, and simulation dispatching
- SIMHYD hydrological model (8-parameter HOOPLA HM15 port of the Chiew et al. 2002 SIMple HYDrological model with exponential infiltration, saturation-proportional interflow/recharge, and dual linear routing reservoirs) support in model registry, config, and simulation dispatching

### Changed
- `day_of_year` is now optional in the calibration API, only required when a snow model is active

## [3.4.4] - 2026-03-21

### Added
- Warmup period filtering for projections: `read_projection_data` now computes an `is_warmup` column marking the first 3 years of each member's time series, and both `_aggregate_projections` and `_evaluate_projection` exclude warmup data from their calculations
- Projection API now sends raw per-member timeseries (`projection`) alongside the aggregated data (`aggregated_projection`), enabling CSV export of the full ensemble
- Horizon dropdown labels now display the date range (e.g., "H50 (2041-01-01 to 2070-12-31)")
- E2E tests verifying exported CSV content for projection data and results (column structure, ensemble member count, indicator values) for both Baskatong and Au Saumon

### Changed
- Projection CSV export now contains the raw per-member timeseries instead of the day-of-year aggregated data, matching student analysis needs

### Fixed
- Projection indicators and interannual hydrographs no longer include warmup period data, which was biasing seasonal statistics
- Unit tests for `_aggregate_projections` and `_evaluate_projection` now include required `is_warmup` column in test DataFrames

## [3.4.3] - 2026-02-21

### Added
- `HolmesFileNotFoundError` exception for distinguishing missing files from malformed data
- Projection module now handles missing projection data gracefully with a user-friendly notification and automatic calibration cleanup

### Changed
- Error messages no longer expose absolute file paths, using filenames only
- Projection data `read_projection_data` raises `HolmesFileNotFoundError` instead of `HolmesDataError` when file is missing

### Fixed
- Simulation and projection APIs now correctly compare snow model against `"none"` string instead of `None`, fixing snow model detection after the 3.4.1 sentinel change
- Simulation API explicitly casts hydro parameters to `float64`, preventing dtype errors when JSON round-trip through JavaScript produces integer values
- Projection file upload now resets previous results, preventing stale charts from persisting
- Projection remove calibration now properly clears config state

## [3.4.2] - 2026-02-20

### Added
- User-configurable `seed` parameter for SCE-UA calibration algorithm, enabling reproducible calibration runs (previously hardcoded to 123)

## [3.4.1] - 2026-02-14

### Fixed
- Fixed calibration bug where selecting transformation "none" (high flows) would break calibration by being incorrectly converted to `null` — the snow model's `null` sentinel was colliding with the transformation's legitimate `"none"` value
- Backend now sends `"none"` as a string instead of `null` for the "no snow model" option, normalizing to `None` only at the API boundary

## [3.4.0] - 2026-01-31

### Added
- CEQUEAU hydrological model support in model registry (`hydro.py`), config, and simulation dispatching
- Warmup period visual indicator (shaded rectangle with label) on simulation streamflow chart
- Parameter description tooltips on manual calibration sliders (hover info icon to see description)
- `description` field in hydro model parameter configurations

### Changed
- Parameter slider step precision increased from 0.1 to 0.01 for non-integer parameters
- Renamed bucket model parameters from descriptive names (`c_soil`, `alpha`, `k_r`, `delta`, `beta`, `k_t`) to generic names (`x1`–`x6`), matching the convention used by GR4J and CEQUEAU
- Calibration bar chart x-axis tick labels are now limited to 10 to prevent overlapping when many iterations are displayed
- Cleaned up model registry docstrings to avoid hardcoded model lists

### Fixed
- Calibration results view now detects stale parameter plots from a previously selected model and re-renders correctly
- Hydro parameters are explicitly cast to `float64` in manual calibration to prevent type errors
- Manual calibration parameter sliders now correctly recreate when switching from a model with more parameters to one with fewer (e.g., CEQUEAU → GR4J)

### Documentation
- Added CEQUEAU model documentation: overview, mathematical formulation from Perrin (2000), 9-parameter description, and differences from original 11-parameter CEQUEAU
- Added comprehensive Concepts documentation with mathematical formulations:
  - GR4J model: production store, unit hydrographs, routing store equations
  - Bucket model: linear reservoir theory, flow partitioning, comparison with GR4J
  - CemaNeige snow model: degree-day method, thermal state, elevation layers
  - Oudin PET: solar geometry calculations, extraterrestrial radiation
  - SCE-UA calibration: algorithm steps, convergence criteria, practical guidance
  - Performance metrics: RMSE, NSE, KGE definitions and interpretation
  - Concepts overview: rainfall-runoff modeling introduction, modeling chain
- Added MathJax configuration for proper LaTeX equation rendering in documentation
- Added auto-generated API reference using mkdocstrings (generates docs from Python docstrings)
- Restructured API reference to mirror Python module hierarchy (one page per module)
- Improved function signature formatting with line wrapping and cross-references
- Written Data Formats documentation: input file formats (observations, CemaNeige info, projections) and export formats
- Fixed reference section to properly include CHANGELOG.md and LICENSE content using include-markdown

## [3.3.8] - 2026-01-24

### Added
- Warmup period exclusion from objective function calculations
  - `read_data()` now returns a tuple `(DataFrame, warmup_steps)` indicating rows before user-requested start date
  - Calibration and simulation metrics are computed only on data after the warmup period
  - SCE-UA calibration passes `warmup_steps` to Rust extension for consistent metric calculation

### Changed
- MkDocs serve now defaults to port 8001 to avoid conflict with HOLMES on port 8000

### Fixed
- CSS selector specificity for warmup rectangle in calibration and simulation charts (changed `rect` to `.warmup-rect`)
- Simulation remove button icon stroke color now uses theme foreground color

### Documentation
- Added MkDocs Material documentation site with full navigation structure
- Created `mkdocs.yml` configuration with Material theme, dark mode, code copy, and MathJax
- Added landing page (`docs/index.md`) with features overview and quick start
- Added GitHub Actions workflow for automatic deployment to GitHub Pages
- Added `mkdocs-include-markdown-plugin` and `mkdocs-git-revision-date-localized-plugin` dependencies
- Written Getting Started guide: installation, quickstart tutorial, and configuration reference
- Written User Guide: interface overview, calibration, simulation, projection, and settings documentation
- Simplified documentation structure: removed Developer Guide section, flattened Concepts/Models and API Reference
- Added Documentation section to CLAUDE.md noting Rust docs location

## [3.3.7] - 2026-01-17

### Added
- Added "Allow save" button in settings to allow reading from saved configs
- Notifications confirming successful file downloads on calibration, simulation, and projection pages
- Brush zoom on calibration, simulation, and projection streamflow plots (drag to zoom, double-click to reset)
- Projection results metrics (winter min, summer min, spring max, autumn max, mean) calculation and scatter plot visualization
- Download of projection results CSV alongside projection timeseries

### Fixed
- Fixed date icon in dark mode for chromium browsers
- Fixed notifications not being removed from the DOM due to missing `data-id` attribute
- Fixed handling of catchments with no snow data
- Config date validation when switching catchments now properly resets start/end if outside available range
- Simulation config "Reset to default" for end date was incorrectly setting to start instead of end
- Changing calibration parameters removes the simulation data

## [3.3.6] - 2026-01-11

### Added
- Labels for manual calibration parameter sliders showing parameter names

### Changed
- Manual calibration settings layout now uses CSS grid for better alignment

### Fixed
- Race condition in simulation page when navigating before configuration data is loaded

## [3.3.5] - 2026-01-11

### Removed
- WebSocket ping/pong heartbeat functionality from frontend and backend (unnecessary for application)

## [3.3.4] - 2026-01-11

### Added
- Custom exception hierarchy in `exceptions.py` for clearer error handling
- Input validation module in `validation.py`
- WebSocket utilities in `utils/websocket.py`
- Comprehensive unit tests achieving 100% code coverage:
  - `tests/unit/test_config.py` for config validation error handling
  - `tests/unit/utils/test_websocket.py` for WebSocket utilities
  - Error handling tests in `test_data.py` for CSV parsing, permissions, and CemaNeige errors
  - Error handling tests in `test_calibration.py`, `test_hydro.py`, `test_snow.py` for Rust exception handling
  - HolmesDataError handling tests in API test files

### Changed
- Updated API modules with improved error handling and validation
- Enhanced calibration, simulation, and projection endpoints
- Improved configuration handling in `config.py`
- Better data loading patterns in `data.py`
- Enhanced logging throughout the application

### Fixed
- Eager file existence checks in `data.py` for `read_catchment_data`, `read_projection_data`, and `_get_available_period` to properly handle missing files with lazy Polars operations
