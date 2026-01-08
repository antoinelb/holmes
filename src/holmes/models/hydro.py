from typing import Callable, Literal, assert_never

import numpy as np
import numpy.typing as npt
from holmes_rs.hydro import gr4j

#########
# types #
#########

HydroModel = Literal["gr4j"]

##########
# public #
##########


def get_config(model: HydroModel) -> list[dict[str, str | float]]:
    match model:
        case "gr4j":
            param_names = gr4j.param_names
            defaults, bounds = gr4j.init()
            return [
                {
                    "name": name,
                    "default": default,
                    "min": bounds_[0],
                    "max": bounds_[1],
                }
                for name, default, bounds_ in zip(
                    param_names, defaults, bounds
                )
            ]
        case _:
            assert_never(model)  # type: ignore


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
        case "gr4j":
            return gr4j.simulate
        case _:
            assert_never(model)  # type: ignore
