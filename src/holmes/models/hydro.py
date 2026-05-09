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
    martine,
    mohyse,
    mordor,
    nam,
    pdm,
    sacramento,
    simhyd,
    smar,
    tank,
    topmodel,
    wageningen,
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
    "martine",
    "mohyse",
    "mordor",
    "nam",
    "pdm",
    "sacramento",
    "simhyd",
    "smar",
    "tank",
    "topmodel",
    "wageningen",
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
            case "martine":
                param_names = martine.param_names
                descriptions = martine.param_descriptions
                defaults, bounds = martine.init()
            case "mohyse":
                param_names = mohyse.param_names
                descriptions = mohyse.param_descriptions
                defaults, bounds = mohyse.init()
            case "mordor":
                param_names = mordor.param_names
                descriptions = mordor.param_descriptions
                defaults, bounds = mordor.init()
            case "nam":
                param_names = nam.param_names
                descriptions = nam.param_descriptions
                defaults, bounds = nam.init()
            case "pdm":
                param_names = pdm.param_names
                descriptions = pdm.param_descriptions
                defaults, bounds = pdm.init()
            case "sacramento":
                param_names = sacramento.param_names
                descriptions = sacramento.param_descriptions
                defaults, bounds = sacramento.init()
            case "simhyd":
                param_names = simhyd.param_names
                descriptions = simhyd.param_descriptions
                defaults, bounds = simhyd.init()
            case "smar":
                param_names = smar.param_names
                descriptions = smar.param_descriptions
                defaults, bounds = smar.init()
            case "tank":
                param_names = tank.param_names
                descriptions = tank.param_descriptions
                defaults, bounds = tank.init()
            case "topmodel":
                param_names = topmodel.param_names
                descriptions = topmodel.param_descriptions
                defaults, bounds = topmodel.init()
            case "wageningen":
                param_names = wageningen.param_names
                descriptions = wageningen.param_descriptions
                defaults, bounds = wageningen.init()
            case "xinanjiang":
                param_names = xinanjiang.param_names
                descriptions = xinanjiang.param_descriptions
                defaults, bounds = xinanjiang.init()
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
        case "martine":
            simulate_fn = martine.simulate
        case "mohyse":
            simulate_fn = mohyse.simulate
        case "mordor":
            simulate_fn = mordor.simulate
        case "nam":
            simulate_fn = nam.simulate
        case "pdm":
            simulate_fn = pdm.simulate
        case "sacramento":
            simulate_fn = sacramento.simulate
        case "simhyd":
            simulate_fn = simhyd.simulate
        case "smar":
            simulate_fn = smar.simulate
        case "tank":
            simulate_fn = tank.simulate
        case "topmodel":
            simulate_fn = topmodel.simulate
        case "wageningen":
            simulate_fn = wageningen.simulate
        case "xinanjiang":
            simulate_fn = xinanjiang.simulate
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
