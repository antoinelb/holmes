import numpy as np
import numpy.typing as npt

def simulate(
    temperature: npt.NDArray[np.float64],
    day_of_year: npt.NDArray[np.uintp],
    latitude: float,
) -> npt.NDArray[np.float64]: ...
