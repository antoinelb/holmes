# Changelog

All notable changes to the holmes Python package will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For changes to the Rust extension, see [src/holmes-rs/CHANGELOG.md](src/holmes-rs/CHANGELOG.md).

## [3.3.7] - 2026-01-17

### Added
- Added "Allow save" button in settings to allow reading from saved configs
- Notifications confirming successful file downloads on calibration, simulation, and projection pages

### Fixed
- Fixed date icon in dark mode for chromium browsers
- Fixed notifications not being removed from the DOM due to missing `data-id` attribute

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
