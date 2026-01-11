# Python Integration Tests

These tests verify the PyO3 bindings work correctly when called from Python.

## Prerequisites

1. Build the `holmes-rs` extension:
   ```bash
   cd /path/to/holmes-rs
   maturin develop --release
   ```

2. Install pytest:
   ```bash
   pip install pytest numpy
   ```

## Running the Tests

From the `tests/python_integration` directory:

```bash
pytest -v
```

Or from the `holmes-rs` directory:

```bash
pytest tests/python_integration -v
```

## Test Coverage

These tests cover the Python bindings for:

- **metrics**: `calculate_rmse`, `calculate_nse`, `calculate_kge`
- **hydro.gr4j**: `init`, `simulate`, `param_names`
- **hydro.bucket**: `init`, `simulate`, `param_names`
- **pet.oudin**: `simulate`
- **snow.cemaneige**: `init`, `simulate`, `param_names`
- **calibration.sce**: `Sce` class with `__init__`, `init`, `step`

## Test Structure

- `conftest.py` - Shared fixtures for test data
- `test_metrics.py` - Tests for metric functions
- `test_hydro.py` - Tests for GR4J and Bucket models
- `test_pet.py` - Tests for Oudin PET calculation
- `test_snow.py` - Tests for CemaNeige snow model
- `test_calibration.py` - Tests for SCE-UA calibration
