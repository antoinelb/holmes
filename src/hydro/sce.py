from typing import Callable, Literal

import numpy as np
import polars as pl
import tqdm

from .utils import Results, evaluate_simulation

##########
# public #
##########


def run_sce_calibration(
    model: Callable,
    data: pl.DataFrame,
    params: dict[str, dict[str, int | float | bool]],
    criteria: Literal["rmse", "nse", "kge"],
    transformation: Literal["log", "sqrt", "none"],
    n_complexes: int,
    n_per_complex: int,
    mings: int,
    nspl: int,
    maxn: int,
    kstop: int,
    pcento: float,
    peps: float,
) -> Results:
    n_params = len(params)
    param_names = list(params.keys())
    lower_bound = np.array([param["min"] for param in params.values()])
    upper_bound = np.array([param["max"] for param in params.values()])

    population = _generate_initial_population(
        n_complexes, n_per_complex, lower_bound, upper_bound
    )
    print(population.shape)
    result, population = _evaluate_population(
        model, data, criteria, transformation, population, param_names
    )
    print(result)


###########
# private #
###########


def _generate_initial_population(
    n_complexes: int,
    n_per_complex: int,
    lower_bound: np.ndarray,
    upper_bound: np.ndarray,
    *,
    seed: int | None = None,
) -> np.ndarray:
    n_population = n_complexes * n_per_complex

    rng = np.random.default_rng(seed)
    return lower_bound + rng.random(
        size=(n_population, lower_bound.shape[0])
    ) * (upper_bound - lower_bound)


def _evaluate_population(
    model: Callable,
    data: pl.DataFrame,
    criteria: Literal["rmse", "nse", "kge"],
    transformation: Literal["log", "sqrt", "none"],
    population: np.ndarray,
    param_names: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    precipitation = data["precipitation"].to_numpy().squeeze()
    evapotranspiration = data["evapotranspiration"].to_numpy().squeeze()
    flow = data["flow"].to_numpy().squeeze()
    result = np.array(
        [
            evaluate_simulation(
                flow,
                model(
                    precipitation,
                    evapotranspiration,
                    **{param: val for param, val in zip(param_names, row)},
                ),
                criteria,
                transformation,
            )
            for row in tqdm.tqdm(population, "Evaluating population...")
        ]
    )
    sort_indices = np.argsort(result)
    result = result[sort_indices]
    population = population[result, :]
    return result, population
