from typing import final

import numpy as np
import numpy.typing as npt

@final
class Sce:
    def __new__(
        cls,
        hydro_model: str,
        snow_model: str | None,
        objective: str,
        transformation: str,
        n_complexes: int,
        k_stop: int,
        p_convergence_threshold: float,
        geometric_range_threshold: float,
        max_evaluations: int,
        seed: int,
    ) -> Sce: ...
    def init(
        self,
        precipitation: npt.NDArray[np.float64],
        temperature: npt.NDArray[np.float64],
        pet: npt.NDArray[np.float64],
        day_of_year: npt.NDArray[np.uintp],
        elevation_layers: npt.NDArray[np.float64],
        median_elevation: float,
        observations: npt.NDArray[np.float64],
    ) -> None: ...
    def step(
        self,
        precipitation: npt.NDArray[np.float64],
        temperature: npt.NDArray[np.float64],
        pet: npt.NDArray[np.float64],
        day_of_year: npt.NDArray[np.uintp],
        elevation_layers: npt.NDArray[np.float64],
        median_elevation: float,
        observations: npt.NDArray[np.float64],
    ) -> tuple[
        bool,
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
        npt.NDArray[np.float64],
    ]: ...
