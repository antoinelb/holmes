# HOLMES

**HydrOLogical Modeling Educational Software**

HOLMES is a web-based hydrological modeling tool designed for teaching operational hydrology. Developed at Université Laval, Québec, Canada.

---

## Features

- **Guided Modeling Pipeline**: stations → weather → model → calibration → simulation → projection, with an interactive station map — every step documented in the [user guide](guide/index.md)
- **Twenty Hydrological Models**: from GR4J to SACRAMENTO, all documented in the [concepts](concepts/index.md) section
- **Snow Modeling**: CemaNeige degree-day model with multi-elevation band support
- **Automatic Calibration**: SCE-UA and DDS optimization algorithms
- **Climate Projections**: ClimEx and ESPO-G6-R2 scenarios fetched per station
- **High Performance**: Rust-powered computational engine with Python integration

---

## Quick Start

Install HOLMES (Python ≥ 3.12):

```bash
pip install holmes-hydro
```

Start the dashboard:

```bash
holmes run
```

Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

The CLI also provides `holmes download` to rebuild the published datasets from their true sources and `holmes experiment` to run batch calibration experiments.

[:material-compass: User guide](guide/index.md){ .md-button .md-button--primary }
[:material-water: Concepts](concepts/index.md){ .md-button }
[:material-file-document: Changelog](reference/changelog.md){ .md-button }

---

## Architecture Overview

HOLMES uses a three-tier architecture:

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Vanilla JavaScript, D3.js, Leaflet | Interactive web interface |
| **Backend** | Python, Starlette, Uvicorn | API routing, data loading, orchestration |
| **Compute** | Rust (holmes-rs), PyO3 | High-performance numerical models |

Communication between frontend and backend uses WebSockets for real-time updates during calibration.

---

## License

HOLMES is released under the [MIT License](reference/license.md).

## Links

- [:fontawesome-brands-github: GitHub Repository](https://github.com/antoinelb/holmes)
- [:fontawesome-brands-python: PyPI Package](https://pypi.org/project/holmes-hydro/)
