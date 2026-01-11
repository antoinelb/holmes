# HOLMES

[![ci holmes](https://github.com/antoinelb/holmes/workflows/ci%20holmes/badge.svg)](https://github.com/antoinelb/holmes/actions)
[![ci holmes-rs](https://github.com/antoinelb/holmes/workflows/ci%20holmes-rs/badge.svg)](https://github.com/antoinelb/holmes/actions)
![holmes-hydro pypi version](https://img.shields.io/pypi/v/holmes-hydro?label=holmes-hydro%20pypi%20package&color=green)
![holmes-rs pypi version](https://img.shields.io/pypi/v/holmes-rs?label=holmes-rs%20pypi%20package&color=green)
[![Supported Python Version](https://img.shields.io/pypi/pyversions/holmes-hydro.svg?color=%2334D058)](https://pypi.org/project/holmes-hydro)

HOLMES (HydrOLogical Modeling Educational Software) is a software developed to teach operational hydrology. It is developed at Université Laval, Québec, Canada.

## Usage

### Installation

```bash
pip install holmes-hydro
```

### Running HOLMES

After installation, start the server with:

```bash
holmes
```

The web interface will be available at http://127.0.0.1:8000.

### Configuration

Customize the server by creating a `.env` file:

```env
DEBUG=True          # Enable debug mode (default: False)
RELOAD=True         # Enable auto-reload on code changes (default: False)
HOST=127.0.0.1      # Server host (default: 127.0.0.1)
PORT=8000           # Server port (default: 8000)
```

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
uv run holmes
```

Or activate the virtual environment and run directly:

```bash
source .venv/bin/activate
holmes
```

### Code Quality

```bash
black src/ tests/
ruff check src/ tests/
ty check src/ tests/
```

## References

- [Bucket Model](https://github.com/ulaval-rs/HOOPLApy/tree/main/hoopla/models/hydro)
