"""
Snow model registry.

This module provides access to snow models (CemaNeige)
implemented in the holmes_rs Rust extension.
"""

import logging
from typing import Callable, Literal, assert_never

import numpy as np
import numpy.typing as npt
from holmes_rs.snow import cemaneige

from holmes.exceptions import (
    HolmesError,
    HolmesNumericalError,
    HolmesValidationError,
)

logger = logging.getLogger("holmes")

#########
# types #
#########

SnowModel = Literal["cemaneige"]

##########
# public #
##########


def get_model(
    model: SnowModel,
) -> Callable[
    [
        npt.NDArray[np.float64],  # params
        npt.NDArray[np.float64],  # precipitation
        npt.NDArray[np.float64],  # temperature
        npt.NDArray[np.uintp],  # day_of_year
        npt.NDArray[np.float64],  # altitude_layers
        float,  # median_altitude
    ],
    npt.NDArray[np.float64],
]:
    """
    Get a wrapped snow model simulation function.

    The returned function wraps the underlying Rust implementation
    with error handling and logging.

    Parameters
    ----------
    model : SnowModel
        Model name ("cemaneige")

    Returns
    -------
    Callable
        Simulation function that takes precipitation, temperature, params,
        day_of_year, altitude_layers, and median_altitude,
        and returns adjusted precipitation
    """
    match model:
        case "cemaneige":
            simulate_fn = cemaneige.simulate
        case _:  # pragma: no cover
            assert_never(model)

    def wrapped_simulate(
        params: npt.NDArray[np.float64],
        precipitation: npt.NDArray[np.float64],
        temperature: npt.NDArray[np.float64],
        day_of_year: npt.NDArray[np.uintp],
        altitude_layers: npt.NDArray[np.float64],
        median_altitude: float,
    ) -> npt.NDArray[np.float64]:
        """Wrapped snow simulation function with error handling."""
        try:
            return simulate_fn(
                params,
                precipitation,
                temperature,
                day_of_year,
                altitude_layers,
                median_altitude,
            )
        except (HolmesNumericalError, HolmesValidationError) as exc:
            logger.error(f"Snow simulation failed for {model}: {exc}")
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception(f"Unexpected error in {model} snow simulation")
            raise HolmesError(f"Snow simulation failed: {exc}") from exc

    return wrapped_simulate
