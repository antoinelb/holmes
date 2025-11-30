from typing import Literal, TypedDict, assert_never

import numpy as np

from . import bucket, gr4j

#########
# types #
#########

hydrological_models = {
    "GR4J": {
        "parameters": gr4j.possible_params,
    },
    "BUCKET": {
        "parameters": bucket.possible_params,
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
        # Clipped to prevent -inf values. The minimum value currently in the
        # data is 0.006617296, so this is still much smaller
        flow = np.log(np.clip(flow, a_min=10**-5, a_max=None))
        simulation = np.log(np.clip(simulation, a_min=10**-5, a_max=None))
    elif transformation == "sqrt":
        flow = np.sqrt(flow)
        simulation = np.sqrt(simulation)

    if criteria == "rmse":
        return float(np.sqrt(np.mean((flow - simulation) ** 2)))
    elif criteria == "nse":
        denominator = np.sum((flow - np.mean(flow)) ** 2)
        if denominator == 0:
            # Constant flow - NSE is undefined
            return -np.inf if not np.allclose(flow, simulation) else 1.0
        return float(1 - np.sum((flow - simulation) ** 2) / denominator)
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
        mean_sim = np.mean(simulation)
        mean_flow = np.mean(flow)
        std_sim = np.std(simulation)
        std_flow = np.std(flow)

        # Handle edge cases
        if mean_sim == 0 or mean_flow == 0:
            # Cannot compute coefficient of variation when mean is zero
            return np.inf if mean_sim != mean_flow else 1.0
        if std_flow == 0:
            # Constant flow - ratio is infinite unless simulation is also constant
            return np.inf if std_sim > 0 else 1.0

        return float((std_sim / mean_sim) / (std_flow / mean_flow))
    elif criteria == "correlation":
        return float(np.corrcoef(flow, simulation)[0, 1])
    else:  # pragma: no cover
        assert_never(criteria)


def get_optimal_for_criteria(
    criteria: Literal[
        "rmse", "nse", "kge", "mean_bias", "deviation_bias", "correlation"
    ],
) -> float:
    return {
        "rmse": 0,
        "nse": 1,
        "kge": 1,
        "mean_bias": 1,
        "deviation_bias": 1,
        "correlation": 1,
    }[criteria]
