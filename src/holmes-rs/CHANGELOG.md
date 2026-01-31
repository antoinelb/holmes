# Changelog

All notable changes to the holmes-rs Rust extension will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-01-31

### Added
- CEQUEAU hydrological model (`hydro::cequeau`) with 9 parameters, surface/groundwater routing, and unit hydrograph delay
- Python bindings and type stubs for the CEQUEAU module (`init`, `simulate`, `param_names`)

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
