# HOLMES

[![ci holmes](https://github.com/antoinelb/holmes/workflows/ci%20holmes/badge.svg)](https://github.com/antoinelb/holmes/actions)
[![ci holmes-rs](https://github.com/antoinelb/holmes/workflows/ci%20holmes-rs/badge.svg)](https://github.com/antoinelb/holmes/actions)
![holmes-hydro pypi version](https://img.shields.io/pypi/v/holmes-hydro?label=holmes-hydro%20pypi%20package&color=green)
![holmes-rs pypi version](https://img.shields.io/pypi/v/holmes-rs?label=holmes-rs%20pypi%20package&color=green)
[![Supported Python Version](https://img.shields.io/pypi/pyversions/holmes-hydro.svg?color=%2334D058)](https://pypi.org/project/holmes-hydro)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://antoinelb.github.io/holmes/)

HOLMES (HydrOLogical Modeling Educational Software) is a software developed to teach operational hydrology. It is developed at Université Laval, Québec, Canada.

📖 **[Documentation](https://antoinelb.github.io/holmes/)** · 📦 **[PyPI](https://pypi.org/project/holmes-hydro/)**

The dashboard guides students through a modeling pipeline — stations → weather → model → calibration → simulation → projection — starting from an interactive map of hydrometric stations.
The backend is Starlette, the frontend is vanilla JavaScript with an Elm architecture (d3 and Leaflet), and communication is mostly over WebSocket.
All numerical computation runs in [holmes-rs](src/holmes-rs), a Rust extension.

## Usage

### Installation

```bash
pip install holmes-hydro
```

### Running HOLMES

After installation, start the dashboard with:

```bash
holmes run
```

The web interface will be available at http://127.0.0.1:8000.

Other commands:

```bash
holmes download     # rebuild the published datasets from their true sources
holmes experiment   # run batch calibration experiments
```

Station, weather, and projection data are fetched from their true sources at runtime and cached under `data/`; prebuilt products are served from the repo so a fresh install works without any credentials.

### Configuration

Customize the server by creating a `.env` file:

```env
DEBUG=True                  # Enable debug mode (default: False)
RELOAD=True                 # Enable auto-reload on code changes (default: False)
HOST=127.0.0.1              # Server host (default: 127.0.0.1)
PORT=8000                   # Server port (default: 8000)
HOLMES_DATA_DIR=data        # Data directory (default: the per-user data
                            # directory, e.g. ~/.local/share/holmes on Linux)
HOLMES_SKIP_DATA_SYNC=True  # Skip the startup data sync (default: False)
```

A repo checkout should set `HOLMES_DATA_DIR=data` to keep using the repo-local `data/` directory.

## Development

### Setup

1. Install [uv](https://docs.astral.sh/uv/):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Clone and install in development mode:
   ```bash
   git clone https://github.com/antoinelb/holmes.git
   cd holmes
   uv sync
   ```

### Running

```bash
uv run holmes run
```

Or activate the virtual environment and run directly:

```bash
source .venv/bin/activate
holmes run
```

### Code Quality

```bash
make static-analysis
```

### Tests

```bash
make test       # unit + integration (100% coverage) and the Rust suites
make test-e2e   # Playwright end-to-end tests
```

## References

- [HOOPLA](https://github.com/ulaval-rs/HOOPLApy/tree/main/hoopla/models/hydro)
