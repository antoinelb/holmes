from . import calibration, hydro, metrics, pet, snow

__version__: str

class HolmesError(Exception):
    """Base exception for HOLMES errors."""

    ...

class HolmesNumericalError(HolmesError):
    """Numerical error during computation."""

    ...

class HolmesValidationError(HolmesError):
    """Validation error for input parameters."""

    ...

__all__ = [
    "__version__",
    "calibration",
    "hydro",
    "metrics",
    "pet",
    "snow",
    "HolmesError",
    "HolmesNumericalError",
    "HolmesValidationError",
]
