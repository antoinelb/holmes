# HOLMES

**HydrOLogical Modeling Educational Software**

HOLMES is a web-based hydrological modeling tool designed for teaching operational hydrology. Developed at Université Laval, Québec, Canada.

---

## Features

- **Multiple Hydrological Models**: GR4J (4 parameters) and Bucket (6 parameters) rainfall-runoff models
- **Snow Modeling**: CemaNeige degree-day model with multi-elevation band support
- **Automatic Calibration**: SCE-UA (Shuffled Complex Evolution) optimization algorithm
- **Climate Projections**: Run future scenarios with calibrated model parameters
- **Interactive Interface**: Real-time parameter adjustment and streamflow visualization
- **High Performance**: Rust-powered computational engine with Python integration

---

## Quick Start

Install HOLMES:

```bash
pip install holmes-hydro
```

Start the server:

```bash
holmes
```

Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).

[:material-rocket-launch: Get Started](getting-started/index.md){ .md-button .md-button--primary }
[:material-book-open-variant: User Guide](user-guide/index.md){ .md-button }

---

## Documentation Sections

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Getting Started**

    ---

    Install HOLMES and run your first simulation in minutes.

    [:octicons-arrow-right-24: Installation](getting-started/installation.md)

-   :material-account-school:{ .lg .middle } **User Guide**

    ---

    Learn how to use the web interface for calibration, simulation, and projection.

    [:octicons-arrow-right-24: User Guide](user-guide/index.md)

-   :material-water:{ .lg .middle } **Concepts**

    ---

    Understand the hydrological models, calibration algorithms, and metrics.

    [:octicons-arrow-right-24: Concepts](concepts/index.md)

-   :material-code-tags:{ .lg .middle } **Developer Guide**

    ---

    Architecture overview and API documentation.

    [:octicons-arrow-right-24: Developer Guide](developer-guide/index.md)

</div>

---

## Architecture Overview

HOLMES uses a three-tier architecture:

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Vanilla JavaScript, D3.js | Interactive web interface |
| **Backend** | Python, Starlette, Uvicorn | API routing, data loading, orchestration |
| **Compute** | Rust (holmes-rs), PyO3 | High-performance numerical models |

Communication between frontend and backend uses WebSockets for real-time updates during calibration.

---

## License

HOLMES is released under the [MIT License](reference/license.md).

## Links

- [:fontawesome-brands-github: GitHub Repository](https://github.com/antoinelb/holmes)
- [:fontawesome-brands-python: PyPI Package](https://pypi.org/project/holmes-hydro/)
