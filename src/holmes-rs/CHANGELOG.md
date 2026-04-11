# Changelog

All notable changes to the holmes-rs Rust extension will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CREC hydrological model (`hydro::crec`) with 6 parameters, sigmoid rainfall-splitting function, and nonlinear surface routing
- Python bindings and type stubs for the CREC module (`init`, `simulate`, `param_names`, `param_descriptions`)
- GARDENIA hydrological model (`hydro::gardenia`) with 6 parameters matching Perrin's thesis GARD structure: overflow-based surface reservoir, quadratic soil emptying, linear groundwater recession, and fractional delay routing
- Python bindings and type stubs for the GARDENIA module (`init`, `simulate`, `param_names`, `param_descriptions`)
- HYMOD hydrological model (`hydro::hymod`) with 6 parameters following the Boyle/Wagener formulation: Pareto-distributed soil moisture store, three linear fast reservoirs in cascade, one linear slow groundwater reservoir, and fractional delay routing
- Python bindings and type stubs for the HYMOD module (`init`, `simulate`, `param_names`, `param_descriptions`)
- HBV hydrological model (`hydro::hbv`) with 9 parameters following the Bergström/Forsman formulation as described in Perrin's thesis (HBV0 / HOOPLA HM6): five-substep soil moisture accounting with nonlinear production, three-reservoir routing with threshold upper outflow, linear lower outflow, and capped percolation, and a triangular unit hydrograph
- Python bindings and type stubs for the HBV module (`init`, `simulate`, `param_names`, `param_descriptions`)
- XINANJIANG hydrological model (`hydro::xinanjiang`) with 8 parameters following Perrin's variant of the Zhao et al. 1980 formulation (HOOPLA HM20): piecewise evapotranspiration, power-distributed saturation-excess production, free-water reservoir with fast/slow routing split, and a two-tap fractional delay unit hydrograph
- Python bindings and type stubs for the XINANJIANG module (`init`, `simulate`, `param_names`, `param_descriptions`)

### Changed
- Made `day_of_year` parameter optional in SCE calibration API (`init`, `step`), consistent with other snow-only parameters
- Renamed `initialize_state` to `init_state` in bucket model for consistency

### Fixed
- SCE calibration no longer crashes with "Zero variance in simulations - KGE undefined" when degenerate parameter sets produce constant model output; worst-case penalty values are assigned instead, and the optimizer continues normally

## [0.3.0] - 2026-01-31

### Added
- CEQUEAU hydrological model (`hydro::cequeau`) with 9 parameters, surface/groundwater routing, and unit hydrograph delay
- Python bindings and type stubs for the CEQUEAU module (`init`, `simulate`, `param_names`)
- `param_descriptions` constant for all hydro models (GR4J, bucket, CEQUEAU) with human-readable parameter descriptions, exposed via Python bindings and type stubs

### Changed
- Renamed bucket model parameters from descriptive names (`c_soil`, `alpha`, `k_r`, `delta`, `beta`, `k_t`) to generic names (`x1`–`x6`), matching the convention used by GR4J and CEQUEAU
- Simplified `WrongModel` error messages to remove hardcoded model lists

## [0.2.3] - 2026-01-24

### Added
- `warmup_steps` parameter to `Sce::init()` and `Sce::step()` methods
  - Allows excluding initial warmup period from objective function calculations
  - Ensures metrics are computed only on the user-requested evaluation period

## [0.2.2] - 2026-01-17

### Changed
- Made snow model parameters (`temperature`, `elevation_bands`, `median_elevation`) optional in SCE calibration API
- Updated `Sce::init()` and `Sce::step()` to accept `Option` types for snow-related parameters
- Calibration without snow model no longer requires temperature or elevation data

### Added
- `MissingSnowParams` error variant to `CalibrationError` for clearer error handling when snow model is configured but required parameters are missing

## [0.2.1] - 2026-01-11

### Added
- Anti-fragility improvements for more robust error handling and recovery
- Comprehensive README with usage examples, model documentation, and API reference
- MIT LICENSE file
- Package metadata in pyproject.toml (authors, license, repository URLs)
- Exception type stubs (`HolmesError`, `HolmesNumericalError`, `HolmesValidationError`) in type hints
