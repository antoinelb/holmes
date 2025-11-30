from pathlib import Path


def _get_package_dir() -> Path:
    """Get path to the holmes package directory."""
    return Path(__file__).parent.parent.resolve()


def _get_data_dir() -> Path:
    """Get path to data directory.

    Works for both:
    - Development: data/ is sibling to holmes/ at src/data/
    - Installed: data/ is inside package at holmes/data/ (via force-include)
    """
    package_dir = _get_package_dir()

    # Check installed location first (inside package)
    installed_data = package_dir / "data"
    if installed_data.exists():
        return installed_data

    # Development location (sibling directory)
    dev_data = package_dir.parent / "data"
    if dev_data.exists():
        return dev_data

    raise FileNotFoundError(
        f"Data directory not found at {installed_data} or {dev_data}"
    )


def _get_static_dir() -> Path:
    """Get path to static directory.

    Works for both:
    - Development: static/ is sibling to holmes/ at src/static/
    - Installed: static/ is inside package at holmes/static/ (via force-include)
    """
    package_dir = _get_package_dir()

    # Check installed location first (inside package)
    installed_static = package_dir / "static"
    if installed_static.exists():
        return installed_static

    # Development location (sibling directory)
    dev_static = package_dir.parent / "static"
    if dev_static.exists():
        return dev_static

    raise FileNotFoundError(
        f"Static directory not found at {installed_static} or {dev_static}"
    )


# Computed once at import time
package_dir = _get_package_dir()
data_dir = _get_data_dir()
static_dir = _get_static_dir()
