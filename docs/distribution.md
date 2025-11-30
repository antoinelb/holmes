# Distributing HOLMES to Students

This document describes how to package and distribute HOLMES for students who may not be familiar with Python or programming.

## Overview

Two distribution methods are documented:

1. **UV-based installation** (recommended) - Students install via a single command
2. **Standalone executables** (Plan B) - Pre-built binaries for each platform

---

## Option 1: UV-Based Distribution (Recommended)

[UV](https://docs.astral.sh/uv/) is a fast Python package manager that can automatically download Python and manage dependencies. This is the recommended approach because:

- Single command installation
- Automatic Python version management
- Cross-platform (Windows, macOS, Linux)
- Easy updates
- Small initial download (~10MB for uv itself)

### Prerequisites for Distribution

Before distributing to students, you need to:

1. **Ensure data files are included in the package**
2. **Publish to PyPI** (or use a Git URL)

#### Step 1: Configure Data File Inclusion

Add the following to `pyproject.toml` to include the `data/` directory in the wheel:

```toml
[tool.uv.build-backend]
module-root = ""
module-name = "src"
data-dir = "data"  # Include data directory
```

Alternatively, if using setuptools in the future, create a `MANIFEST.in`:

```
recursive-include data *
recursive-include src/static *
```

#### Step 2: Update Path Resolution

The current `src/utils/paths.py` uses relative paths that won't work when installed as a package. Update it to handle both development and installed modes:

```python
from pathlib import Path
import importlib.resources

def get_root_dir() -> Path:
    """Get the root directory, works both in dev and installed mode."""
    # In development: use relative path
    dev_root = Path(__file__).parent.parent.parent
    if (dev_root / "data").exists():
        return dev_root

    # When installed: use importlib.resources
    # Data files are installed alongside the package
    with importlib.resources.as_file(
        importlib.resources.files("src").parent
    ) as pkg_path:
        return pkg_path

root_dir = get_root_dir()
```

#### Step 3: Build and Publish to PyPI

```bash
# Build the package
uv build

# Upload to PyPI (requires PyPI account and API token)
uv publish

# Or upload to TestPyPI first for testing
uv publish --index-url https://test.pypi.org/simple/
```

### Student Installation Instructions

Provide students with these instructions based on their operating system:

#### Windows

1. Open PowerShell and run:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

2. Close and reopen PowerShell, then install HOLMES:
   ```powershell
   uv tool install holmes
   ```

3. Run HOLMES:
   ```powershell
   holmes
   ```

4. Open your browser to http://127.0.0.1:8000

#### macOS / Linux

1. Open Terminal and run:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install HOLMES:
   ```bash
   uv tool install holmes
   ```

3. Run HOLMES:
   ```bash
   holmes
   ```

4. Open your browser to http://127.0.0.1:8000

### Alternative: Install from Git (Before PyPI Publication)

If you haven't published to PyPI yet, students can install directly from Git:

```bash
# Install from GitHub
uv tool install git+https://github.com/yourorg/holmes.git

# Or from a specific branch/tag
uv tool install git+https://github.com/yourorg/holmes.git@v3.2.0
```

### Alternative: One-Time Execution with uvx

For quick testing without permanent installation:

```bash
# Run directly without installing (downloads each time)
uvx holmes

# Or from Git
uvx git+https://github.com/yourorg/holmes.git
```

### Updating HOLMES

When you release a new version:

```bash
# Students run this to update
uv tool upgrade holmes
```

### Creating an Install Script

For an even simpler experience, provide students with a script they can download and run:

**install-holmes.sh** (macOS/Linux):
```bash
#!/bin/bash
set -e

echo "Installing HOLMES..."

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.local/bin/env
fi

# Install HOLMES
uv tool install holmes

echo ""
echo "HOLMES installed successfully!"
echo "Run 'holmes' to start the application."
echo "Then open http://127.0.0.1:8000 in your browser."
```

**install-holmes.ps1** (Windows):
```powershell
Write-Host "Installing HOLMES..."

# Install uv if not present
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv package manager..."
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","User") + ";" + [System.Environment]::GetEnvironmentVariable("Path","Machine")
}

# Install HOLMES
uv tool install holmes

Write-Host ""
Write-Host "HOLMES installed successfully!"
Write-Host "Run 'holmes' to start the application."
Write-Host "Then open http://127.0.0.1:8000 in your browser."
```

---

## Option 2: Standalone Executables (Plan B)

If UV-based installation proves problematic for some students, you can build standalone executables using PyInstaller or Nuitka.

### Known Limitations

- **Numba JIT**: Has compatibility issues with PyInstaller; may require `--collect-all numba`
- **File size**: Expect 300-500MB per platform
- **Build complexity**: Must build separately for each platform
- **Debugging**: Harder to diagnose issues in bundled executables

### Using PyInstaller

#### Install PyInstaller

```bash
uv add --dev pyinstaller
```

#### Create PyInstaller Spec File

Create `holmes.spec` in the project root:

```python
# holmes.spec
import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

a = Analysis(
    ['src/__main__.py'],
    pathex=[str(root)],
    binaries=[],
    datas=[
        ('data', 'data'),
        ('src/static', 'src/static'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'numba',
        'scipy.special._cdflib',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='holmes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep True - students need to see the server URL
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='holmes',
)
```

#### Build the Executable

```bash
# Activate the virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# Build
pyinstaller holmes.spec

# Output will be in dist/holmes/
```

#### Platform-Specific Builds

You must build on each target platform. Use GitHub Actions for automation:

**.github/workflows/build-executables.yml**:
```yaml
name: Build Executables

on:
  release:
    types: [published]
  workflow_dispatch:

jobs:
  build:
    strategy:
      matrix:
        include:
          - os: windows-latest
            artifact: holmes-windows
          - os: macos-latest
            artifact: holmes-macos
          - os: ubuntu-latest
            artifact: holmes-linux

    runs-on: ${{ matrix.os }}

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: |
          uv sync
          uv add pyinstaller

      - name: Build executable
        run: uv run pyinstaller holmes.spec

      - name: Create archive (Windows)
        if: matrix.os == 'windows-latest'
        run: Compress-Archive -Path dist/holmes -DestinationPath ${{ matrix.artifact }}.zip

      - name: Create archive (Unix)
        if: matrix.os != 'windows-latest'
        run: tar -czvf ${{ matrix.artifact }}.tar.gz -C dist holmes

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: |
            ${{ matrix.artifact }}.zip
            ${{ matrix.artifact }}.tar.gz
```

### Using Nuitka (Alternative to PyInstaller)

Nuitka compiles Python to C, potentially offering better performance and smaller size.

```bash
# Install Nuitka
uv add --dev nuitka

# Build (Linux/macOS)
uv run python -m nuitka \
    --standalone \
    --include-data-dir=data=data \
    --include-data-dir=src/static=src/static \
    --include-module=numba \
    --include-module=uvicorn \
    src/__main__.py

# Build (Windows) - add these flags
# --windows-console-mode=force
```

### Distribution of Executables

1. **Create a release** on GitHub with the built archives attached
2. **Provide clear instructions**:

```
HOLMES Installation (Standalone Version)

1. Download the appropriate file for your system:
   - Windows: holmes-windows.zip
   - macOS: holmes-macos.tar.gz
   - Linux: holmes-linux.tar.gz

2. Extract the archive to a folder of your choice

3. Run the application:
   - Windows: Double-click holmes.exe
   - macOS/Linux: Open terminal, navigate to folder, run ./holmes

4. Open http://127.0.0.1:8000 in your browser

Note: On macOS, you may need to right-click and select "Open"
the first time to bypass Gatekeeper.
```

---

## Troubleshooting

### UV Installation Issues

**"uv: command not found"** after installation:
- Close and reopen the terminal
- On Windows, restart PowerShell as administrator

**Python version errors**:
- UV will automatically download Python 3.13 if needed
- If blocked by firewall, download Python 3.13 manually from python.org

**Permission errors on Windows**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### PyInstaller Issues

**Numba errors at runtime**:
- Add `--collect-all numba` to pyinstaller command
- Or add to spec file: `collect_all('numba')`

**Missing modules**:
- Check console output for import errors
- Add missing modules to `hiddenimports` in spec file

**Large file size**:
- Use UPX compression (already enabled in spec)
- Consider using `--onefile` for single executable (slower startup)

### Application Issues

**Port already in use**:
```bash
# Find and kill process using port 8000
# Linux/macOS:
lsof -i :8000
kill -9 <PID>

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Slow first startup**:
- Normal - Numba compiles functions on first run
- Subsequent runs will be faster
- The `/precompile` endpoint can be called to warm up

---

## Comparison Summary

| Aspect | UV Installation | Standalone Executable |
|--------|-----------------|----------------------|
| User complexity | Run 2 commands | Download, extract, run |
| Download size | ~200MB (deps) | ~400MB per platform |
| Build complexity | Push to PyPI | Build on 3+ platforms |
| Updates | `uv tool upgrade` | Re-download |
| Debugging | Standard Python | Difficult |
| Numba compatibility | Full | May have issues |

**Recommendation**: Start with UV-based distribution. Only fall back to executables if students consistently have issues with UV installation.
