"""
Calibration model registry and orchestration.

This module provides calibration algorithms (SCE-UA) and orchestrates
the calibration process using snow and hydro models.
"""

import asyncio
import logging
from typing import Any, Awaitable, Callable, Literal, assert_never

import numpy as np
import numpy.typing as npt
from holmes.exceptions import (
    HolmesError,
    HolmesNumericalError,
    HolmesValidationError,
)
from holmes_rs.calibration.sce import Sce

from . import snow
from .snow import SnowModel

logger = logging.getLogger("holmes")

#########
# types #
#########

Objective = Literal["rmse", "nse", "kge"]
Transformation = Literal["log", "sqrt", "none"]
Algorithm = Literal["sce"]

##########
# public #
##########


def get_config(
    model: Algorithm,
) -> list[dict[str, str | int | float | bool | None]]:
    """Get calibration algorithm configuration."""
    match model:
        case "sce":
            return [
                {
                    "name": "n_complexes",
                    "min": 1,
                    "max": None,
                    "default": 25,
                    "integer": True,
                },
                {
                    "name": "k_stop",
                    "min": 1,
                    "max": None,
                    "default": 10,
                    "integer": True,
                },
                {
                    "name": "p_convergence_threshold",
                    "min": 0,
                    "max": 1,
                    "default": 0.1,
                    "integer": False,
                },
                {
                    "name": "geometric_range_threshold",
                    "min": 0,
                    "max": None,
                    "default": 0.001,
                    "integer": False,
                },
                {
                    "name": "max_evaluations",
                    "min": 1,
                    "max": None,
                    "default": 5000,
                    "integer": True,
                },
            ]
        case _:  # pragma: no cover
            assert_never(model)


async def calibrate(
    precipitation: npt.NDArray[np.float64],
    temperature: npt.NDArray[np.float64] | None,
    pet: npt.NDArray[np.float64],
    observations: npt.NDArray[np.float64],
    day_of_year: npt.NDArray[np.uintp],
    elevation_layers: npt.NDArray[np.float64] | None,
    median_elevation: float | None,
    qnbv: float | None,
    warmup_steps: int,
    hydro_model: str,
    snow_model: SnowModel | None,
    objective: Objective,
    transformation: Transformation,
    algorithm: Algorithm,
    params: dict[str, Any],
    *,
    callback: (
        Callable[
            [
                bool,
                npt.NDArray[np.float64],
                npt.NDArray[np.float64],
                dict[str, float],
            ],
            Awaitable[None],
        ]
        | None
    ) = None,
    stop_event: asyncio.Event | None = None,
) -> npt.NDArray[np.float64]:
    seed = 123
    max_iter = 100_000

    if snow_model is not None:
        if (
            temperature is None
            or elevation_layers is None
            or median_elevation is None
            or qnbv is None
        ):
            raise HolmesError("There are missing snow parameters.")
        try:
            snow_simulate = snow.get_model(snow_model)
            snow_params = np.array([0.25, 3.74, qnbv])
            precipitation = snow_simulate(
                snow_params,
                precipitation,
                temperature,
                day_of_year,
                elevation_layers,
                median_elevation,
            )
        except (HolmesNumericalError, HolmesValidationError) as exc:
            logger.error(f"Snow simulation failed during calibration: {exc}")
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception(
                "Unexpected error in snow simulation during calibration"
            )
            raise HolmesError(f"Snow simulation failed: {exc}") from exc

    match algorithm:
        case "sce":
            try:
                calibration = Sce(
                    hydro_model,
                    None,
                    objective,
                    transformation,
                    seed=seed,
                    n_complexes=params["n_complexes"],
                    k_stop=params["k_stop"],
                    p_convergence_threshold=params["p_convergence_threshold"],
                    geometric_range_threshold=params[
                        "geometric_range_threshold"
                    ],
                    max_evaluations=params["max_evaluations"],
                )
            except (HolmesNumericalError, HolmesValidationError) as exc:
                logger.error(f"Failed to initialize SCE-UA: {exc}")
                raise
            except Exception as exc:  # pragma: no cover
                logger.exception("Unexpected error initializing SCE-UA")
                raise HolmesError(
                    f"SCE-UA initialization failed: {exc}"
                ) from exc

            try:
                calibration.init(
                    precipitation,
                    temperature,
                    pet,
                    day_of_year,
                    elevation_layers,
                    median_elevation,
                    observations,
                    warmup_steps,
                )
            except (HolmesNumericalError, HolmesValidationError) as exc:
                logger.error(f"Failed to initialize SCE-UA with data: {exc}")
                raise
            except Exception as exc:  # pragma: no cover
                logger.exception(
                    "Unexpected error during SCE-UA data initialization"
                )
                raise HolmesError(
                    f"SCE-UA data initialization failed: {exc}"
                ) from exc

            for _ in range(max_iter):
                try:
                    done, params_, simulation, objectives = calibration.step(
                        precipitation,
                        temperature,
                        pet,
                        day_of_year,
                        elevation_layers,
                        median_elevation,
                        observations,
                        warmup_steps,
                    )
                except (HolmesNumericalError, HolmesValidationError) as exc:
                    logger.error(f"SCE-UA step failed: {exc}")
                    raise
                except Exception as exc:  # pragma: no cover
                    logger.exception("Unexpected error during SCE-UA step")
                    raise HolmesError(f"SCE-UA step failed: {exc}") from exc

                results = {
                    "rmse": objectives[0],
                    "nse": objectives[1],
                    "kge": objectives[2],
                }
                if callback is not None:
                    await callback(done, params_, simulation, results)
                # Yield control to allow I/O processing (e.g., receiving stop message)
                await asyncio.sleep(0.001)
                if stop_event is not None and stop_event.is_set():
                    break
                if done:
                    break

            return np.array(params_)

        case _:  # pragma: no cover
            assert_never(algorithm)  # type: ignore
