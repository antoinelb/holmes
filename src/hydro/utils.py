from typing import Literal, TypedDict, assert_never

import numpy as np

from . import gr4j

#########
# types #
#########

hydrological_models = {
    "GR4J": {
        "parameters": gr4j.possible_params,
    },
}


class Results(TypedDict):
    params: dict[str, list[float]]
    objective: list[float]


##########
# public #
##########


def evaluate_simulation(
    flow: np.ndarray,
    simulation: np.ndarray,
    criteria: Literal["rmse", "nse", "kge"],
    transformation: Literal["log", "sqrt", "none"],
) -> float:
    if transformation == "log":
        flow = np.log(flow)
        simulation = np.log(simulation)
    elif transformation == "sqrt":
        flow = np.sqrt(flow)
        simulation = np.sqrt(simulation)

    if criteria == "rmse":
        return float(np.sqrt(np.mean((flow - simulation) ** 2)))
    elif criteria == "nse":
        return float(
            1
            - np.sum((flow - simulation) ** 2)
            / np.sum((flow - np.mean(flow)) ** 2)
        )
    elif criteria == "kge":
        r = float(np.corrcoef(flow, simulation)[0, 1])
        bm = float(np.mean(simulation) / np.mean(flow))
        bv = float(
            (np.std(simulation) / np.mean(simulation))
            / (np.std(flow) / np.mean(flow))
        )
        return 1 - ((1 - r) ** 2 + (1 - bm) ** 2 + (1 - bv) ** 2) ** 0.5
    else:
        assert_never(criteria)


def get_optimal_for_criteria(
    criteria: Literal["rmse", "nse", "kge"],
) -> float:
    return {"rmse": 0, "nse": 1, "kge": 1}[criteria]
