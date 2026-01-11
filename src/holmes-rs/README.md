# holmes-rs

A fast, production-ready collection of hydrological models implemented in Rust with Python bindings via PyO3.

**holmes-rs** is the computational engine behind [HOLMES](https://github.com/antoinelb/holmes) (HydrOLogical Modeling Educational Software), but is designed to be usable as a standalone library for anyone needing efficient hydrological simulations.

## Features

- **Hydrological Models**: GR4J and Bucket rainfall-runoff models
- **Snow Modeling**: CemaNeige snow accumulation and melt model
- **PET Calculation**: Oudin method for potential evapotranspiration
- **Calibration**: SCE-UA (Shuffled Complex Evolution) optimization algorithm
- **Metrics**: RMSE, NSE, and KGE objective functions
- **Performance**: Pure Rust with SIMD-friendly array operations via ndarray
- **Python Integration**: Full NumPy interoperability through PyO3

## Installation

### From PyPI (when published)

```bash
pip install holmes-rs
```

### From Source

Requires Rust 1.70+ and Python 3.11+.

```bash
cd src/holmes-rs
pip install maturin
maturin develop --release
```

## Quick Start

### Python

```python
import numpy as np
from holmes_rs.hydro import gr4j
from holmes_rs.pet import oudin
from holmes_rs.metrics import calculate_nse

# Generate PET from temperature
temperature = np.random.uniform(5, 25, 365)
day_of_year = np.arange(1, 366)
latitude = 45.0
pet = oudin.simulate(temperature, day_of_year, latitude)

# Initialize GR4J with default parameters
defaults, bounds = gr4j.init()
# defaults: [350.0, 0.0, 90.0, 1.7]  (x1, x2, x3, x4)
# bounds: [[10, 1500], [-5, 3], [10, 400], [0.8, 10]]

# Run simulation
precipitation = np.random.uniform(0, 20, 365)
streamflow = gr4j.simulate(defaults, precipitation, pet)

# Evaluate against observations
observations = np.random.uniform(0, 10, 365)
nse = calculate_nse(observations, streamflow)
print(f"NSE: {nse:.3f}")
```

### Rust

```rust
use holmes_rs::hydro::gr4j;
use holmes_rs::metrics::calculate_nse;
use ndarray::array;

let (defaults, _bounds) = gr4j::init();
let precipitation = array![5.0, 10.0, 0.0, 15.0, 2.0];
let pet = array![3.0, 3.5, 4.0, 3.2, 3.8];

let streamflow = gr4j::simulate(
    defaults.view(),
    precipitation.view(),
    pet.view()
).unwrap();

let nse = calculate_nse(observations.view(), streamflow.view()).unwrap();
```

## Models

### GR4J

A parsimonious 4-parameter rainfall-runoff model widely used in operational hydrology.

| Parameter | Range | Description |
|-----------|-------|-------------|
| x1 | 10–1500 | Production store capacity (mm) |
| x2 | -5–3 | Groundwater exchange coefficient (mm/day) |
| x3 | 10–400 | Routing store capacity (mm) |
| x4 | 0.8–10 | Unit hydrograph time base (days) |

```python
from holmes_rs.hydro import gr4j

defaults, bounds = gr4j.init()
streamflow = gr4j.simulate(params, precipitation, pet)
```

### Bucket

A 6-parameter conceptual model with explicit soil, routing, and transpiration reservoirs.

| Parameter | Range | Description |
|-----------|-------|-------------|
| c_soil | 10–1000 | Soil storage capacity (mm) |
| alpha | 0–1 | Infiltration partitioning |
| k_r | 1–200 | Routing decay constant |
| delta | 2–10 | Routing delay (timesteps) |
| beta | 0–1 | Baseflow coefficient |
| k_t | 1–400 | Transpiration parameter |

```python
from holmes_rs.hydro import bucket

defaults, bounds = bucket.init()
streamflow = bucket.simulate(params, precipitation, pet)
```

### CemaNeige

A degree-day snow model with multi-layer elevation distribution.

| Parameter | Range | Description |
|-----------|-------|-------------|
| ctg | 0–1 | Thermal state time constant |
| kf | 0–20 | Snowmelt rate coefficient (mm/°C/day) |
| qnbv | 50–800 | Degree-day factor threshold |

```python
from holmes_rs.snow import cemaneige

defaults, bounds = cemaneige.init()

# elevation_layers: fraction of catchment at each elevation band
# median_elevation: reference elevation (m)
effective_precip = cemaneige.simulate(
    params, precipitation, temperature, day_of_year,
    elevation_layers, median_elevation
)

# Chain with hydro model
streamflow = gr4j.simulate(hydro_params, effective_precip, pet)
```

### Oudin PET

Temperature-based potential evapotranspiration using extraterrestrial radiation.

```python
from holmes_rs.pet import oudin

pet = oudin.simulate(temperature, day_of_year, latitude)
```

## Calibration

SCE-UA (Shuffled Complex Evolution - University of Arizona) for automatic parameter optimization.

```python
from holmes_rs.calibration.sce import Sce

# Create calibrator
sce = Sce(
    hydro_model="gr4j",
    snow_model=None,            # or "cemaneige"
    objective="nse",            # "rmse", "nse", or "kge"
    transformation="none",      # "none", "log", or "sqrt"
    n_complexes=3,
    k_stop=5,
    p_convergence_threshold=0.1,
    geometric_range_threshold=0.0001,
    max_evaluations=1000,
    seed=42                     # for reproducibility
)

# Initialize with data
sce.init(precip, temp, pet, doy, elevation_layers, median_elev, observations)

# Run calibration
done = False
while not done:
    done, best_params, criteria, objectives = sce.step(
        precip, temp, pet, doy, elevation_layers, median_elev, observations
    )
    print(f"Best NSE so far: {max(objectives):.4f}")

print(f"Optimal parameters: {best_params}")
```

### Objective Functions

| Objective | Formula | Optimal |
|-----------|---------|---------|
| RMSE | √(Σ(O-S)²/n) | 0 |
| NSE | 1 - Σ(O-S)²/Σ(O-μ)² | 1 |
| KGE | 1 - √((r-1)² + (α-1)² + (β-1)²) | 1 |

### Transformations

Apply transformations to emphasize different flow regimes:
- `none`: Raw values (emphasizes high flows)
- `log`: Log-transformed (emphasizes low flows)
- `sqrt`: Square-root (balanced)

## Metrics

Standalone metric functions for model evaluation:

```python
from holmes_rs.metrics import calculate_rmse, calculate_nse, calculate_kge

rmse = calculate_rmse(observations, simulations)
nse = calculate_nse(observations, simulations)
kge = calculate_kge(observations, simulations)
```

## Error Handling

holmes-rs provides informative exceptions for debugging:

```python
from holmes_rs import HolmesValidationError, HolmesNumericalError

try:
    # Invalid: negative precipitation
    gr4j.simulate(params, np.array([-1.0, 5.0]), pet)
except HolmesValidationError as e:
    print(f"Validation failed: {e}")

try:
    # Edge case: constant observations (zero variance)
    calculate_nse(np.array([5.0, 5.0, 5.0]), simulations)
except HolmesNumericalError as e:
    print(f"Numerical issue: {e}")
```

## Module Structure

```
holmes_rs
├── hydro
│   ├── gr4j      # GR4J model
│   └── bucket    # Bucket model
├── snow
│   └── cemaneige # CemaNeige snow model
├── pet
│   └── oudin     # Oudin PET method
├── calibration
│   └── sce       # SCE-UA optimizer
└── metrics       # RMSE, NSE, KGE
```

## Development

```bash
# Run Rust tests
cargo test

# Run Rust tests with coverage
cargo +nightly llvm-cov

# Run Python integration tests
pytest tests/python_integration

# Format and lint
cargo fmt
cargo clippy
```

## Performance Notes

- All numerical operations use ndarray with optimized BLAS
- Calibration uses Rayon for parallel objective function evaluation
- Release builds use LTO for maximum performance

## License

MIT License - see [LICENSE](LICENSE) for details.

## Part of HOLMES

This library powers the computational backend of [HOLMES v3](https://github.com/antoinelb/holmes), a web-based hydrological modeling tool for teaching operational hydrology. While developed primarily for HOLMES, holmes-rs is designed as a general-purpose hydrological modeling library suitable for research, education, and operational applications.
