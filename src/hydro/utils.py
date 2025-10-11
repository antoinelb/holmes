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
    criteria: Literal[
        "rmse", "nse", "kge", "mean_bias", "deviation_bias", "correlation"
    ],
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
        correlation = evaluate_simulation(
            flow, simulation, "correlation", "none"
        )
        mean_bias = evaluate_simulation(flow, simulation, "mean_bias", "none")
        deviation_bias = evaluate_simulation(
            flow, simulation, "deviation_bias", "none"
        )
        return (
            1
            - (
                (1 - correlation) ** 2
                + (1 - mean_bias) ** 2
                + (1 - deviation_bias) ** 2
            )
            ** 0.5
        )
    elif criteria == "mean_bias":
        return float(np.mean(simulation) / np.mean(flow))
    elif criteria == "deviation_bias":
        return float(
            (np.std(simulation) / np.mean(simulation))
            / (np.std(flow) / np.mean(flow))
        )
    elif criteria == "correlation":
        return float(np.corrcoef(flow, simulation)[0, 1])
    else:
        assert_never(criteria)


def get_optimal_for_criteria(
    criteria: Literal["rmse", "nse", "kge"],
) -> float:
    return {"rmse": 0, "nse": 1, "kge": 1}[criteria]


def evaluate_simulation_on_multiple_criteria(
    flow: np.ndarray, simulation: np.ndarray
) -> dict[str, float]:
    return {
        "nse_high": evaluate_simulation(flow, simulation, "nse", "none"),
        "nse_medium": evaluate_simulation(flow, simulation, "nse", "sqrt"),
        "nse_low": evaluate_simulation(flow, simulation, "nse", "log"),
        "water_balance": evaluate_simulation(
            flow, simulation, "mean_bias", "none"
        ),
        "flow_variability": evaluate_simulation(
            flow, simulation, "deviation_bias", "none"
        ),
        "correlation": evaluate_simulation(
            flow, simulation, "correlation", "none"
        ),
    }
