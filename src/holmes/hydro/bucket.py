import math

import numba
import numpy as np
from jaxtyping import Float

#########
# types #
#########

possible_params = {
    "C_soil": {  # soil reservoir capacity (mm)
        "min": 10,
        "max": 1000,
        "is_integer": False,
    },
    "alpha": {  # soil reservoir overflow dissociation constant (-)
        "min": 0,
        "max": 1,
        "is_integer": False,
    },
    "k_R": {  # slow routing reservoir empltying constant (days)
        "min": 1,
        "max": 200,
        "is_integer": False,
    },
    "delta": {  # routing delay (days)
        "min": 2,
        "max": 10,
        "is_integer": False,
    },
    "beta": {  # rainfall partitioning coefficient (-)
        "min": 0,
        "max": 1,
        "is_integer": False,
    },
    "k_T": {  # general routing time constant (days)
        "min": 1,
        "max": 400,
        "is_integer": False,
    },
}

##########
# public #
##########


@numba.jit(nopython=True, cache=True)
def run_model(
    precipitation: Float[np.ndarray, "t"],  # noqa: F821
    evapotranspiration: Float[np.ndarray, "t"],  # noqa: F821
    *,
    C_soil: float,
    alpha: float,
    k_R: float,
    delta: float,
    beta: float,
    k_T: float,
) -> Float[np.ndarray, "t"]:  # noqa: F821
    S, R, T, DL, HY = _initialize_state(C_soil, alpha, k_R, delta, beta, k_T)

    streamflows: list[float] = []
    for t in range(precipitation.shape[0]):
        Q_sim, S, R, T, DL, HY = _run_step(
            precipitation[t],
            evapotranspiration[t],
            C_soil,
            alpha,
            k_R,
            delta,
            beta,
            k_T,
            S,
            R,
            T,
            DL,
            HY,
        )
        streamflows.append(Q_sim)

    return np.array(streamflows)


async def precompile() -> None:
    run_model(
        np.array([1.0]),
        np.array([1.0]),
        **{param: val["min"] for param, val in possible_params.items()},
    )


###########
# private #
###########


@numba.jit(nopython=True, cache=True)
def _initialize_state(
    C_soil: float,
    alpha: float,
    k_R: float,
    delta: float,
    beta: float,
    k_T: float,
) -> tuple[
    float,
    float,
    float,
    Float[np.ndarray, "n"],  # noqa: F821
    Float[np.ndarray, "n"],  # noqa: F821
]:
    """
    Initializes the state variables

    Parameters
    ----------
    C_soil : float
        Soil reservoir capacity (mm)
    alpha : float
        Slow routing reservoir empltying constant (-)
    k_R : float
        Slow routing reservoir empltying constant (days)
    delta : float
        Routing delay (days)
    beta : float
        Rainfall partitioning coefficient (-)
    k_T : float
        General routing time constant (days)

    Returns
    -------
    S : float
        Level of the soil moisture reservoir (mm)
    R : float
        Level of the slow routing reservoir (mm)
    T : float
        Level of the fast routing reservoir (mm)
    DL : Float[np.ndarray, "n"]
        Delay distribution array for routing lag
    HY : Float[np.ndarray, "n"]
        Hydrograph array for delayed flow
    """
    # initialization of the reservoir states
    S = C_soil * 0.5
    R = 10
    T = 5

    # array of ints from 0 to the routing delay
    k = np.arange(math.ceil(delta), dtype=np.float64)

    DL = np.zeros_like(k)
    DL[-2] = 1 / (delta - k[-2] + 1)
    DL[-1] = 1 - DL[-2]

    HY = np.zeros_like(k)

    return S, R, T, DL, HY


@numba.jit(nopython=True, cache=True)
def _run_step(
    P: float,
    E: float,
    C_soil: float,
    alpha: float,
    k_R: float,
    delta: float,
    beta: float,
    k_T: float,
    S: float,
    R: float,
    T: float,
    DL: Float[np.ndarray, "n"],  # noqa: F821
    HY: Float[np.ndarray, "n"],  # noqa: F821
) -> tuple[
    float,
    float,
    float,
    float,
    Float[np.ndarray, "n"],  # noqa: F821
    Float[np.ndarray, "n"],  # noqa: F821
]:
    """
    Runs a single step of the model.

    Parameters
    ----------
    P : float
        Precipitation
    E : float
        Evapotranspiration
    C_soil : float
        Soil reservoir capacity (mm)
    alpha : float
        Slow routing reservoir empltying constant (-)
    k_R : float
        Slow routing reservoir empltying constant (days)
    delta : float
        Routing delay (days)
    beta : float
        Rainfall partitioning coefficient (-)
    k_T : float
        General routing time constant (days)
    S : float
        Level of the soil moisture reservoir (mm)
    R : float
        Level of the slow routing reservoir (mm)
    T : float
        Level of the fast routing reservoir (mm)
    DL : Float[np.ndarray, "n"]
        Delay distribution array for routing lag
    HY : Float[np.ndarray, "n"]
        Hydrograph array for delayed flow

    Returns
    -------
    Q : float
        Simulated streamflow
    S : float
        Updated level of the soil moisture reservoir (mm)
    R : float
        Updated level of the slow routing reservoir (mm)
    T : float
        Updated Level of the fast routing reservoir (mm)
    DL : Float[np.ndarray, "n"]
        Updated delay distribution array for routing lag
    HY : Float[np.ndarray, "n"]
        Updated hydrograph array for delayed flow
    """
    # slow flow precipitation
    P_s = (1 - beta) * P
    # fast flow precipitation
    P_r = beta * P

    # soil moisture accounting
    if P_s >= E:  # wet conditions
        S = S + P_s - E
        I_s = max(0, S - C_soil)
        S = S - I_s
    else:  # dry conditions
        S = S * math.exp((P_s - E) / C_soil)
        I_s = 0

    # slow routing component
    R = R + I_s * (1 - alpha)
    Q_r = R / (k_R * k_T)
    R = R - Q_r

    # fast routing
    T = T + P_r + I_s * alpha
    Q_t = T / k_T
    T = T - Q_t

    # shift hydrograph one step
    HY[:-1] = HY[1:]
    HY[-1] = 0.0

    # total flow calculation
    HY = HY + DL * (Q_t + Q_r)
    Q_sim = max(0, HY[0])  # simulated streamflow

    return Q_sim, S, R, T, DL, HY
