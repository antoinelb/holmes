from typing import Callable, Literal, assert_never

import numpy as np
import numpy.typing as npt
from holmes_rs.snow import cemaneige

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
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        npt.NDArray[np.uintp],
        npt.NDArray[np.float64],
        float,
    ],
    npt.NDArray[np.float64],
]:
    match model:
        case "cemaneige":
            return cemaneige.simulate
        case _:
            assert_never(model)  # type: ignore
