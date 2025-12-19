# HOLMES Test Suite

This directory contains the test suite for HOLMES v3.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── fixtures/                # Test data and mock responses
├── unit/                    # Unit tests (fast, isolated)
│   ├── test_api/
│   ├── test_data/
│   ├── test_hydro/
│   └── test_utils/
└── integration/             # Integration tests (slower, end-to-end)
    └── test_frontend_integration.py  # Playwright browser tests
```

## Running Tests

### All Tests
```bash
pytest
```

### Skip Slow Tests
```bash
pytest -m "not slow"
```

### With Coverage Report
```bash
pytest --cov=holmes --cov-report=html
open htmlcov/index.html
```

### Parallel Execution
```bash
pytest -n auto
```

## Test Markers

Tests are marked with the following markers:

- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Tests that take >1s
- `@pytest.mark.requires_data` - Tests needing data files

## Writing Tests

**Important:** This project uses **function-based tests**, not class-based tests.

See `docs/function-based-testing-guide.md` for the complete guide.

### Example Function-Based Test

```python
import pytest
from holmes.hydro import gr4j


@pytest.fixture
def sample_inputs():
    """Sample precipitation and evapotranspiration data."""
    precip = np.array([10, 20, 30])
    evap = np.array([2, 3, 4])
    return precip, evap


def test_gr4j_returns_array_same_length(sample_inputs):
    """GR4J should return flow array with same length as input."""
    precip, evap = sample_inputs
    flow = gr4j.run_model(precip, evap, x1=350, x2=0.0, x3=50, x4=2.0)
    assert len(flow) == len(precip)
```

## Coverage Goals

| Module | Target Coverage | Priority |
|--------|----------------|----------|
| `holmes/hydro/utils.py` | 100% | HIGH |
| `holmes/hydro/gr4j.py` | 95% | HIGH |
| `holmes/hydro/sce.py` | 90% | HIGH |
| `holmes/data.py` | 95% | HIGH |
| `holmes/api/*.py` | 90% | HIGH |

## Debugging Failed Tests

```bash
# Run with debugger
pytest --pdb

# Last failed tests only
pytest --lf

# Failed tests first
pytest --ff

# Extra verbosity
pytest -vv
```

## CI/CD Integration

Tests are automatically run in CI/CD on every push. All tests must pass before merging.

## More Information

- Full test plan: `docs/test-plan.md`
- Function-based testing guide: `docs/function-based-testing-guide.md`
- Test examples: `docs/test-examples.md`
