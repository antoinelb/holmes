import numpy as np
import numpy.typing as npt

param_names: list[str]

def init() -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]: ...
def simulate(
    params: npt.NDArray[np.float64],
    precipitation: npt.NDArray[np.float64],
    pet: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]: ...
