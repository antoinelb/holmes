from typing import Literal, assert_never

import numpy as np
import numpy.typing as npt
from holmes.models import calibration
from holmes_rs.metrics import calculate_kge, calculate_nse, calculate_rmse

##########
# public #
##########


def evaluate(
    observations: npt.NDArray[np.float64],
    simulation: npt.NDArray[np.float64],
    criteria: (
        calibration.Objective
        | Literal["mean_bias", "deviation_bias", "correlation"]
    ),
    transformation: calibration.Transformation,
) -> float:
    if transformation == "log":
        # Clipped to prevent -inf values. The minimum value currently in the
        # data is 0.006617296, so this is still much smaller
        observations = np.log(np.clip(observations, a_min=10**-5, a_max=None))
        simulation = np.log(np.clip(simulation, a_min=10**-5, a_max=None))
    elif transformation == "sqrt":
        observations = np.sqrt(observations)
        simulation = np.sqrt(simulation)

    if criteria == "rmse":
        return calculate_rmse(observations, simulation)
    elif criteria == "nse":
        return calculate_nse(observations, simulation)
    elif criteria == "kge":
        return calculate_kge(observations, simulation)
    elif criteria == "mean_bias":
        return float(np.mean(simulation) / np.mean(observations))
    elif criteria == "deviation_bias":
        mean_sim = np.mean(simulation)
        mean_observations = np.mean(observations)
        std_sim = np.std(simulation)
        std_observations = np.std(observations)

        # Handle edge cases
        if mean_sim == 0 or mean_observations == 0:
            # Cannot compute coefficient of variation when mean is zero
            return np.inf if mean_sim != mean_observations else 1.0
        if std_observations == 0:
            # Constant observations - ratio is infinite unless simulation is also constant
            return np.inf if std_sim > 0 else 1.0

        return float(
            (std_sim / mean_sim) / (std_observations / mean_observations)
        )
    elif criteria == "correlation":
        return float(np.corrcoef(observations, simulation)[0, 1])
    else:  # pragma: no cover
        assert_never(criteria)  # type: ignore
