# HOLMES

## Software description
HOLMES (HydrOLogical Modeling Educationnal Software) is a software developped to teach operational hydrology. It is developed at the university Laval, Québec, Canada.

## Installation

### Using uv (recommended for development)

1. Install uv if you haven't already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install the package in development mode:
   ```bash
   uv sync
   ```

This will install HOLMES and all its dependencies in a virtual environment managed by uv.

### Using pip

1. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Linux/Mac
   # or
   .venv\Scripts\activate  # On Windows
   ```

2. Install the package:
   ```bash
   pip install -e .
   ```

## Running HOLMES

### Using the CLI command (recommended)

After installation, you can run HOLMES using the command-line interface:

```bash
holmes
```

Or use the shorthand:

```bash
h
```

The server will start on http://127.0.0.1:8000 by default.

### Using Python directly

You can also run HOLMES directly with Python:

```bash
python -m src
```

### Configuration

You can customize the server behavior by creating a `.env` file in the project root with the following options:

```env
DEBUG=True          # Enable debug mode (default: False)
RELOAD=True         # Enable auto-reload on code changes (default: False)
HOST=127.0.0.1      # Server host (default: 127.0.0.1)
PORT=8000           # Server port (default: 8000)
```
