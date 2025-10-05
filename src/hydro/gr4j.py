import math

import numba
import numpy as np

#########
# types #
#########

possible_params = {
    "x1": {
        "min": 10,
        "max": 1500,
        "is_integer": True,
    },
    "x2": {
        "min": -5,
        "max": 3,
        "is_integer": False,
    },
    "x3": {
        "min": 10,
        "max": 400,
        "is_integer": True,
    },
    "x4": {
        "min": 0.8,
        "max": 10.0,
        "is_integer": False,
    },
}

##########
# public #
##########


@numba.jit(nopython=True)
def run_model(
    precipitation: np.ndarray,
    evapotranspiration: np.ndarray,
    *,
    x1: int,
    x2: float,
    x3: int,
    x4: float,
) -> np.ndarray:
    flows: list[float] = []

    production_store, routing_store = _get_initial_stores(x1, x3)
    unit_hydrographs = _create_unit_hydrographs(x4)
    hydrographs = (
        np.zeros_like(unit_hydrographs[0]),
        np.zeros_like(unit_hydrographs[1]),
    )

    for t in range(precipitation.shape[0]):
        production_store, routing_precipitation = _update_production(
            production_store,
            float(precipitation[t]),
            float(evapotranspiration[t]),
            x1,
        )
        routing_store, hydrographs, flow = _update_routing(
            routing_store,
            hydrographs,
            unit_hydrographs,
            routing_precipitation,
            x2,
            x3,
        )
        flows.append(float(flow))

    return np.array(flows)


async def precompile_model() -> None:
    run_model(
        np.array([1.0]),
        np.array([1.0]),
        **{param: val["min"] for param, val in possible_params.items()},
    )


###########
# private #
###########


@numba.jit(nopython=True)
def _get_initial_stores(x1: float, x3: float):
    production_store = x1 / 2
    routing_store = x3 / 2
    return production_store, routing_store


@numba.jit(nopython=True)
def _create_unit_hydrographs(x4: float) -> tuple[np.ndarray, np.ndarray]:
    if int(x4) == x4:
        s_curve_1 = np.power(np.arange(x4 + 1) / x4, 1.25)
        s_curve_2 = np.concatenate(
            (
                0.5 * np.power(np.arange(x4 + 1) / x4, 1.25),
                1
                - 0.5 * np.power(2 - np.arange(x4 + 1, 2 * x4 + 1) / x4, 1.25),
            )
        )
    else:
        s_curve_1 = np.power(
            np.clip(np.arange(math.ceil(x4) + 1) / x4, None, 1), 1.25
        )
        s_curve_2 = np.concatenate(
            (
                0.5 * np.power(np.arange(math.floor(x4) + 1) / x4, 1.25),
                1
                - 0.5
                * np.power(
                    np.clip(
                        2
                        - np.arange(math.ceil(x4), math.ceil(2 * x4) + 1) / x4,
                        0,
                        None,
                    ),
                    1.25,
                ),
            )
        )

    unit_hydrograph_1 = s_curve_1[1:] - s_curve_1[:-1]
    unit_hydrograph_2 = s_curve_2[1:] - s_curve_2[:-1]

    return unit_hydrograph_1, unit_hydrograph_2


@numba.jit(nopython=True)
def _update_production(
    store: float, precipitation: float, evapotranspiration: float, x1: float
) -> tuple[float, float]:
    if precipitation > evapotranspiration:
        # only calculate terms once
        tmp_term_1 = store / x1
        tmp_term_2 = math.tanh(precipitation / x1)

        store_precipitation = (
            x1
            * (1 - tmp_term_1**2)
            * tmp_term_2
            / (1 + tmp_term_1 * tmp_term_2)
        )
        store = store + store_precipitation
    elif precipitation < evapotranspiration:
        tmp_term_1 = store / x1
        # only calculate terms once
        tmp_term_2 = math.tanh(evapotranspiration / x1)
        evapotranspiration = (
            store
            * (2 - tmp_term_1)
            * tmp_term_2
            / (1 + (1 - tmp_term_1) * tmp_term_2)
        )
        store = store - evapotranspiration
        store_precipitation = 0
    else:
        store_precipitation = 0

    if x1 / store > 1e-3:
        percolation = store * (
            1 - (1 + (4 / 21 * store / x1) ** 4) ** (-1 / 4)
        )
        store = store - percolation
    else:
        percolation = 0

    routing_precipitation = precipitation - store_precipitation + percolation

    return store, routing_precipitation


@numba.jit(nopython=True)
def _update_routing(
    store: float,
    hydrographs: tuple[np.ndarray, np.ndarray],
    unit_hydrographs: tuple[np.ndarray, np.ndarray],
    routing_precipitation: float,
    x2: float,
    x3: float,
) -> tuple[float, tuple[np.ndarray, np.ndarray], float]:

    hydrographs = _update_hydrographs(
        routing_precipitation, hydrographs, unit_hydrographs
    )

    Q9 = float(hydrographs[0][0])
    Q1 = float(hydrographs[1][0])

    groundwater_exchange = x2 * (store / x3) ** 3.5

    store = max(store + Q9 + groundwater_exchange, 1e-3 * x3)

    routed_flow = store * (1 - (1 + (store / x3) ** 4) ** (-1 / 4))
    store = store - routed_flow

    direct_flow = max(0, Q1 + groundwater_exchange)

    total_flow = routed_flow + direct_flow

    return store, hydrographs, total_flow


@numba.jit(nopython=True)
def _update_hydrographs(
    routing_precipitation: float,
    hydrographs: tuple[np.ndarray, np.ndarray],
    unit_hydrographs: tuple[np.ndarray, np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    # shift existing water forward in time
    hydrographs[0][:-1] = hydrographs[0][1:]
    hydrographs[1][:-1] = hydrographs[1][1:]

    # clear last position
    hydrographs[0][-1] = 0
    hydrographs[1][-1] = 0

    # distribute precipitation based on unit hydrograph
    hydrographs = (
        hydrographs[0] + 0.9 * routing_precipitation * unit_hydrographs[0],
        hydrographs[1] + 0.1 * routing_precipitation * unit_hydrographs[1],
    )

    return hydrographs
