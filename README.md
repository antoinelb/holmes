# HOLMES

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
   git clone https://gitlab.com/antoinelb/holmes.git
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

### Testing

```bash
uv run pytest
```

### Code Quality

```bash
uv run black src/ tests/
uv run ruff check src/ tests/
uv run ty check src/
```

## References

- [Bucket Model](https://github.com/ulaval-rs/HOOPLApy/tree/main/hoopla/models/hydro)
