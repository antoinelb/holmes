# Changelog

All notable changes to the holmes Python package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For changes to the Rust extension, see [src/holmes-rs/CHANGELOG.md](src/holmes-rs/CHANGELOG.md).

<!-- changelog-start -->

## [3.4.0] - 2026-01-31

### Added
- CEQUEAU hydrological model support in model registry (`hydro.py`), config, and simulation dispatching
- Warmup period visual indicator (shaded rectangle with label) on simulation streamflow chart

### Changed
- Parameter slider step precision increased from 0.1 to 0.01 for non-integer parameters
- Calibration bar chart x-axis tick labels are now limited to 10 to prevent overlapping when many iterations are displayed

### Fixed
- Calibration results view now detects stale parameter plots from a previously selected model and re-renders correctly
- Hydro parameters are explicitly cast to `float64` in manual calibration to prevent type errors

### Documentation
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
