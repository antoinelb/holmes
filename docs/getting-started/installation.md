# Installation

HOLMES can be installed via pip (recommended for users) or from source (for development).

## Requirements

- **Python 3.11** or newer
- A modern web browser
- Operating systems: Linux, macOS, or Windows

## Installing via pip

The simplest way to install HOLMES is using pip:

```bash
pip install holmes-hydro
```

This installs both the `holmes-hydro` Python package and the `holmes-rs` Rust extension that provides high-performance model computations.

### Verify Installation

After installation, verify that HOLMES is correctly installed:

```bash
holmes --version
```

This should display the installed version number.

## Installing from Source

For development or to access the latest features, install from the GitHub repository.

### Step 1: Install uv

HOLMES uses [uv](https://docs.astral.sh/uv/) for package management:

=== "Linux/macOS"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

### Step 2: Clone the Repository

```bash
git clone https://github.com/antoinelb/holmes.git
cd holmes
```

### Step 3: Install Dependencies

```bash
uv sync
```

This creates a virtual environment and installs all dependencies, including building the Rust extension.

### Step 4: Run HOLMES

With the virtual environment activated:

```bash
uv run holmes
```

Or activate the environment first:

```bash
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
holmes
```

## Troubleshooting

### Common Issues

#### "Command not found: holmes"

If you installed via pip but the `holmes` command isn't found:

1. Ensure your Python scripts directory is in your PATH
2. Try running with the full path: `python -m holmes`

#### Rust Compilation Errors

If installing from source and encountering Rust errors:

1. Ensure you have Rust installed: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
2. Update Rust: `rustup update`
3. Retry the installation

#### Port Already in Use

If port 8000 is already occupied:

```bash
# Create a .env file to use a different port
echo "PORT=8001" > .env
holmes
```

See [Configuration](configuration.md) for more options.

### Getting Help

If you encounter issues:

1. Check the [GitHub Issues](https://github.com/antoinelb/holmes/issues) for known problems
2. Open a new issue with your error message and system information

## Next Steps

- Follow the [Quickstart](quickstart.md) to run your first calibration
- Configure the server using [Configuration](configuration.md) options
