"""
Configuration module for HOLMES.

Loads configuration from environment variables and .env file,
with validation to ensure values are within acceptable ranges.
"""

import warnings

from starlette.config import Config

from holmes.exceptions import HolmesConfigError
from holmes.validation import validate_host, validate_port

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore", category=UserWarning, module="starlette.config"
    )
    config = Config(".env")

DEBUG = config("DEBUG", cast=bool, default=False)
RELOAD = config("RELOAD", cast=bool, default=False)

# Load and validate PORT
_port = config("PORT", cast=int, default=8000)
try:
    PORT = validate_port(_port)
except ValueError as exc:
    raise HolmesConfigError(str(exc)) from exc

# Load and validate HOST
_host = config("HOST", default="127.0.0.1")
try:
    HOST = validate_host(_host)
except ValueError as exc:
    raise HolmesConfigError(str(exc)) from exc
