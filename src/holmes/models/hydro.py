"""
Hydrological model registry.

This module provides access to hydrological models (bucket, GR4J)
implemented in the holmes_rs Rust extension.
"""

import logging
from typing import Callable, Literal, assert_never

import numpy as np
import numpy.typing as npt
from holmes_rs.hydro import bucket, gr4j

from holmes.exceptions import (
    HolmesError,
    HolmesNumericalError,
    HolmesValidationError,
)

logger = logging.getLogger("holmes")

#########
# types #
#########

HydroModel = Literal["bucket", "gr4j"]

##########
# public #
##########


def get_config(model: HydroModel) -> list[dict[str, str | float]]:
    """
    Get model parameter configuration.

    Parameters
    ----------
    model : HydroModel
        Model name ("bucket" or "gr4j")

    Returns
    -------
    list[dict]
        List of parameter configurations with name, default, min, max
    """
    try:
        match model:
            case "bucket":
                param_names = bucket.param_names
                defaults, bounds = bucket.init()
            case "gr4j":
                param_names = gr4j.param_names
                defaults, bounds = gr4j.init()
            case _:  # pragma: no cover
                assert_never(model)
    except (HolmesNumericalError, HolmesValidationError) as exc:
        logger.error(f"Failed to initialize {model} model: {exc}")
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception(f"Unexpected error initializing {model} model")
        raise HolmesError(f"Failed to initialize model: {exc}") from exc

    return [
        {
            "name": name,
            "default": default,
            "min": bounds_[0],
            "max": bounds_[1],
        }
        for name, default, bounds_ in zip(param_names, defaults, bounds)
    ]


def get_model(
    model: HydroModel,
) -> Callable[
    [
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
    ],
    npt.NDArray[np.float64],
]:
    """
    Get a wrapped model simulation function.

    The returned function wraps the underlying Rust implementation
    with error handling and logging.

    Parameters
    ----------
    model : HydroModel
        Model name ("bucket" or "gr4j")

    Returns
    -------
    Callable
        Simulation function that takes (params, precipitation, pet)
        and returns streamflow
    """
    match model:
        case "bucket":
            simulate_fn = bucket.simulate
        case "gr4j":
            simulate_fn = gr4j.simulate
        case _:  # pragma: no cover
            assert_never(model)

    def wrapped_simulate(
        params: npt.NDArray[np.float64],
        precipitation: npt.NDArray[np.float64],
        pet: npt.NDArray[np.float64],
    ) -> npt.NDArray[np.float64]:
        """Wrapped simulation function with error handling."""
        try:
            return simulate_fn(params, precipitation, pet)
        except (HolmesNumericalError, HolmesValidationError) as exc:
            logger.error(f"Simulation failed for {model}: {exc}")
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception(f"Unexpected error in {model} simulation")
            raise HolmesError(f"Simulation failed: {exc}") from exc

    return wrapped_simulate
