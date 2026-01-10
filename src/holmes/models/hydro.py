from typing import Callable, Literal, assert_never

import numpy as np
import numpy.typing as npt
from holmes_rs.hydro import bucket, gr4j

#########
# types #
#########

HydroModel = Literal["bucket", "gr4j"]

##########
# public #
##########


def get_config(model: HydroModel) -> list[dict[str, str | float]]:
    match model:
        case "bucket":
            param_names = bucket.param_names
            defaults, bounds = bucket.init()
        case "gr4j":
            param_names = gr4j.param_names
            defaults, bounds = gr4j.init()
        case _:  # pragma: no cover
            assert_never(model)
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
    match model:
        case "bucket":
            return bucket.simulate
        case "gr4j":
            return gr4j.simulate
        case _:  # pragma: no cover
            assert_never(model)
