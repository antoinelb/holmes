import logging
from typing import Callable, Literal, assert_never

import numpy as np
import numpy.typing as npt
from holmes.exceptions import (
    HolmesError,
    HolmesNumericalError,
    HolmesValidationError,
)
from holmes_rs.hydro import (
    bucket,
    cequeau,
    crec,
    gardenia,
    gr4j,
    hbv,
    hymod,
    ihacres,
    nam,
    sacramento,
    topmodel,
    xinanjiang,
)

logger = logging.getLogger("holmes")

#########
# types #
#########

HydroModel = Literal[
    "gr4j",
    "bucket",
    "cequeau",
    "crec",
    "gardenia",
    "hbv",
    "hymod",
    "ihacres",
    "nam",
    "sacramento",
    "topmodel",
    "xinanjiang",
]

##########
# public #
##########


def get_config(model: HydroModel) -> list[dict[str, str | float]]:
    """
    Get model parameter configuration.

    Parameters
    ----------
    model : HydroModel
        Model name (see HydroModel for valid options)

    Returns
    -------
    list[dict]
        List of parameter configurations with name, default, min, max,
        description
    """
    try:
        match model:
            case "gr4j":
                param_names = gr4j.param_names
                descriptions = gr4j.param_descriptions
                defaults, bounds = gr4j.init()
            case "bucket":
                param_names = bucket.param_names
                descriptions = bucket.param_descriptions
                defaults, bounds = bucket.init()
            case "cequeau":
                param_names = cequeau.param_names
                descriptions = cequeau.param_descriptions
                defaults, bounds = cequeau.init()
            case "crec":
                param_names = crec.param_names
                descriptions = crec.param_descriptions
                defaults, bounds = crec.init()
            case "gardenia":
                param_names = gardenia.param_names
                descriptions = gardenia.param_descriptions
                defaults, bounds = gardenia.init()
            case "hbv":
                param_names = hbv.param_names
                descriptions = hbv.param_descriptions
                defaults, bounds = hbv.init()
            case "hymod":
                param_names = hymod.param_names
                descriptions = hymod.param_descriptions
                defaults, bounds = hymod.init()
            case "ihacres":
                param_names = ihacres.param_names
                descriptions = ihacres.param_descriptions
                defaults, bounds = ihacres.init()
            case "nam":
                param_names = nam.param_names
                descriptions = nam.param_descriptions
                defaults, bounds = nam.init()
            case "sacramento":
                param_names = sacramento.param_names
                descriptions = sacramento.param_descriptions
                defaults, bounds = sacramento.init()
            case "topmodel":
                param_names = topmodel.param_names
                descriptions = topmodel.param_descriptions
                defaults, bounds = topmodel.init()
            case "xinanjiang":
                param_names = xinanjiang.param_names
                descriptions = xinanjiang.param_descriptions
                defaults, bounds = xinanjiang.init()
            case _:  # pragma: no cover
                assert_never(model)  # type: ignore
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
            "description": desc,
        }
        for name, desc, default, bounds_ in zip(
            param_names, descriptions, defaults, bounds
        )
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
        Model name (see HydroModel for valid options)

    Returns
    -------
    Callable
        Simulation function that takes (params, precipitation, pet)
        and returns streamflow
    """
    match model:
        case "gr4j":
            simulate_fn = gr4j.simulate
        case "bucket":
            simulate_fn = bucket.simulate
        case "cequeau":
            simulate_fn = cequeau.simulate
        case "crec":
            simulate_fn = crec.simulate
        case "gardenia":
            simulate_fn = gardenia.simulate
        case "hbv":
            simulate_fn = hbv.simulate
        case "hymod":
            simulate_fn = hymod.simulate
        case "ihacres":
            simulate_fn = ihacres.simulate
        case "nam":
            simulate_fn = nam.simulate
        case "sacramento":
            simulate_fn = sacramento.simulate
        case "topmodel":
            simulate_fn = topmodel.simulate
        case "xinanjiang":
            simulate_fn = xinanjiang.simulate
        case _:  # pragma: no cover
            assert_never(model)  # type: ignore

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
