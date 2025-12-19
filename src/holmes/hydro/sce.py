"""
Shuffled Complex Evolution (SCE-UA) calibration algorithm.

Functional implementation based on:
- Duan, Q., Sorooshian, S., & Gupta, V. K. (1992). Effective and efficient
  global optimization for conceptual rainfall-runoff models. Water Resources
  Research, 28(4), 1015-1031.
"""

import asyncio
import random
from typing import Awaitable, Callable, Literal

import numba
import numpy as np
import polars as pl

from .utils import Results, evaluate_simulation

##########
# public #
##########


async def run_sce_calibration(
    model: Callable,
    data: pl.DataFrame,
    params: dict[str, dict[str, int | float | bool]],
    criteria: Literal["rmse", "nse", "kge"],
    transformation: Literal["log", "sqrt", "none"],
    n_complexes: int,
    n_per_complex: int,
    min_complexes: int,
    n_evolution_steps: int,
    max_evaluations: int,
    kstop: int,
    pcento: float,
    peps: float,
    progress_callback: Callable[[dict], Awaitable[None]] | None = None,
) -> Results:
    """
    Run SCE-UA calibration algorithm.

    Parameters:
        model: Model function to calibrate
        data: DataFrame with precipitation, evapotranspiration, flow
        params: Parameter definitions with min, max, is_integer
        criteria: Objective function (rmse, nse, kge)
        transformation: Data transformation (log, sqrt, none)
        n_complexes: Number of complexes (ngs)
        n_per_complex: Number of points per complex (npg)
        min_complexes: Minimum complexes (mings, unused in current impl)
        n_evolution_steps: Evolution steps per complex (nspl)
        max_evaluations: Maximum function evaluations (maxn)
        kstop: Convergence window size
        pcento: Percent change threshold for convergence
        peps: Normalized geometric range threshold
        progress_callback: Optional async callback for progress updates

    Returns:
        Results with parameter evolution history and objective values
    """
    # Setup
    n_params = len(params)
    param_names = list(params.keys())
    lower_bounds = np.array([p["min"] for p in params.values()])
    upper_bounds = np.array([p["max"] for p in params.values()])
    n_simplex = n_params + 1

    # Extract data once for efficiency
    precipitation = data["precipitation"].to_numpy().squeeze()
    evapotranspiration = data["evapotranspiration"].to_numpy().squeeze()
    flow = data["flow"].to_numpy().squeeze()

    # Determine if we minimize or maximize
    is_minimization = criteria == "rmse"

    # Generate initial population
    initial_point = (lower_bounds + upper_bounds) / 2
    population = _generate_initial_population(
        n_complexes,
        n_per_complex,
        lower_bounds,
        upper_bounds,
        initial_point=initial_point,
    )

    # Evaluate initial population
    icall = 0
    objectives = np.zeros(population.shape[0])
    for i in range(population.shape[0]):
        simulation = model(
            precipitation,
            evapotranspiration,
            **{
                param: (
                    int(val) if params[param]["is_integer"] else float(val)
                )
                for param, val in zip(param_names, population[i, :])
            },
        )
        objectives[i] = evaluate_simulation(
            flow, simulation, criteria, transformation
        )
        icall += 1

    # Sort population (ascending for minimization, descending for maximization)
    if is_minimization:
        sort_idx = np.argsort(objectives)
    else:
        sort_idx = np.argsort(-objectives)

    objectives = objectives[sort_idx]
    population = population[sort_idx, :]

    # Track best point and history
    bestx = population[0, :].copy()
    bestf = objectives[0]
    BESTX = [bestx.copy()]
    BESTF = [bestf]

    # Convergence tracking
    gnrng = _compute_normalized_geometric_range(
        population, lower_bounds, upper_bounds
    )
    criter = [bestf]
    criter_change = 1e5
    iteration = 0

    # Main SCE loop
    while icall < max_evaluations and gnrng > peps and criter_change > pcento:
        # Partition into complexes
        complexes, complex_objectives = _partition_into_complexes(
            population, objectives, n_complexes
        )

        # Evolve each complex
        for igs in range(n_complexes):
            cx = complexes[igs]
            cf = complex_objectives[igs]

            # Evolve complex nspl times
            for _ in range(n_evolution_steps):
                # Select simplex
                simplex_indices = _select_simplex_indices(
                    n_per_complex, n_simplex
                )
                s = cx[simplex_indices, :]
                sf = cf[simplex_indices]

                # Competitive Complex Evolution (with evaluation)
                snew, fnew, icall = _competitive_complex_evolution(
                    s,
                    sf,
                    lower_bounds,
                    upper_bounds,
                    model,
                    precipitation,
                    evapotranspiration,
                    params,
                    param_names,
                    flow,
                    criteria,
                    transformation,
                    icall,
                )

                # Replace worst point in simplex
                s[-1, :] = snew
                sf[-1] = fnew

                # Reintegrate simplex into complex
                cx[simplex_indices, :] = s
                cf[simplex_indices] = sf

                # Sort complex
                if is_minimization:
                    sort_idx = np.argsort(cf)
                else:
                    sort_idx = np.argsort(-cf)
                cf = cf[sort_idx]
                cx = cx[sort_idx, :]

            # Update complex
            complexes[igs] = cx
            complex_objectives[igs] = cf

        # Merge complexes
        population, objectives = _merge_complexes(
            complexes, complex_objectives, is_minimization
        )

        # Record best point
        bestx = population[0, :].copy()
        bestf = objectives[0]
        BESTX.append(bestx.copy())
        BESTF.append(bestf)

        # Compute convergence metrics
        gnrng = _compute_normalized_geometric_range(
            population, lower_bounds, upper_bounds
        )
        criter.append(bestf)

        if iteration >= kstop:
            criter_change = (
                abs(criter[-1] - criter[-kstop])
                * 100
                / np.mean(np.abs(criter[-kstop:]))
            )

        iteration += 1

        # Send progress update
        if progress_callback is not None:
            # Format current history for progress update
            BESTX_current = np.array(BESTX)
            await progress_callback(
                {
                    "type": "progress",
                    "iteration": iteration,
                    "evaluations": icall,
                    "best_objective": float(bestf),
                    "best_params": {
                        param: float(val)
                        for param, val in zip(param_names, bestx)
                    },
                    "gnrng": float(gnrng),
                    "percent_change": float(criter_change),
                    "params_history": {
                        param: BESTX_current[:, i].tolist()
                        for i, param in enumerate(param_names)
                    },
                    "objective_history": BESTF.copy(),
                }
            )

        # Yield control to event loop
        await asyncio.sleep(0)

    # Format results
    BESTX_array = np.array(BESTX)
    return {
        "params": {
            param: BESTX_array[:, i].tolist()
            for i, param in enumerate(param_names)
        },
        "objective": BESTF,
    }


###########
# private #
###########


def _generate_initial_population(
    n_complexes: int,
    n_per_complex: int,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
    initial_point: np.ndarray | None = None,
    seed: int | None = None,
) -> np.ndarray:
    """Generate initial population using uniform random sampling."""
    n_population = n_complexes * n_per_complex
    rng = np.random.default_rng(seed)

    population = lower_bounds + rng.random(
        size=(n_population, lower_bounds.shape[0])
    ) * (upper_bounds - lower_bounds)

    # Include initial point if provided
    if initial_point is not None:
        population[0, :] = initial_point

    return population


def _partition_into_complexes(
    population: np.ndarray,
    objectives: np.ndarray,
    n_complexes: int,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """
    Partition population into complexes using systematic sampling.

    Each complex gets every n_complexes-th member.
    """
    n_per_complex = population.shape[0] // n_complexes
    complexes = []
    complex_objectives = []

    for igs in range(n_complexes):
        k1 = np.arange(n_per_complex)
        k2 = k1 * n_complexes + igs

        cx = population[k2, :].copy()
        cf = objectives[k2].copy()

        complexes.append(cx)
        complex_objectives.append(cf)

    return complexes, complex_objectives


def _merge_complexes(
    complexes: list[np.ndarray],
    complex_objectives: list[np.ndarray],
    is_minimization: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Merge complexes back into single population and sort."""
    population = np.vstack(complexes)
    objectives = np.concatenate(complex_objectives)

    # Sort
    if is_minimization:
        sort_idx = np.argsort(objectives)
    else:
        sort_idx = np.argsort(-objectives)

    return population[sort_idx, :], objectives[sort_idx]


def _select_simplex_indices(
    n_per_complex: int,
    n_simplex: int,
) -> np.ndarray:
    """
    Select simplex from complex using triangular probability distribution.

    Favors better points in the sorted complex.
    """
    indices = np.zeros(n_simplex, dtype=int)
    indices[0] = 0  # Always include best point

    for k in range(1, n_simplex):
        # Try to find unique index
        for _ in range(1000):
            # Triangular distribution (from v2 implementation)
            lpos = int(
                np.floor(
                    n_per_complex
                    + 0.5
                    - np.sqrt(
                        (n_per_complex + 0.5) ** 2
                        - n_per_complex * (n_per_complex + 1) * random.random()
                    )
                )
            )

            # Check if unique
            if lpos not in indices[:k]:
                break

        indices[k] = lpos

    return np.sort(indices)


def _competitive_complex_evolution(
    simplex: np.ndarray,
    simplex_objectives: np.ndarray,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
    model: Callable,
    precipitation: np.ndarray,
    evapotranspiration: np.ndarray,
    params: dict,
    param_names: list[str],
    flow: np.ndarray,
    criteria: Literal["rmse", "nse", "kge"],
    transformation: Literal["log", "sqrt", "none"],
    icall: int,
    alpha: float = 1.0,
    beta: float = 0.5,
) -> tuple[np.ndarray, float, int]:
    """
    Competitive Complex Evolution - evolve simplex using Nelder-Mead operations.

    Steps:
    1. Reflection: snew = centroid + alpha * (centroid - worst)
    2. If out of bounds: random point
    3. Evaluate reflection
    4. If worse than worst: Contraction
    5. If contraction worse: random point

    Returns new point, its objective value, and updated call count.
    """
    # Worst point and objective
    sw = simplex[-1, :]
    fw = simplex_objectives[-1]

    # Centroid (excluding worst)
    ce = np.mean(simplex[:-1, :], axis=0)

    # Helper function to evaluate a point
    def evaluate_point(point: np.ndarray) -> float:
        simulation = model(
            precipitation,
            evapotranspiration,
            **{
                param: int(val) if params[param]["is_integer"] else float(val)
                for param, val in zip(param_names, point)
            },
        )
        return evaluate_simulation(flow, simulation, criteria, transformation)

    # Reflection
    snew = ce + alpha * (ce - sw)

    # Check bounds
    if np.any(snew < lower_bounds) or np.any(snew > upper_bounds):
        # Generate random point
        snew = lower_bounds + np.random.random(lower_bounds.shape[0]) * (
            upper_bounds - lower_bounds
        )

    # Evaluate reflection point
    fnew = evaluate_point(snew)
    icall += 1

    # If reflection failed (worse than worst), try contraction
    if fnew > fw:
        snew = sw + beta * (ce - sw)
        fnew = evaluate_point(snew)
        icall += 1

        # If contraction also failed, use random point
        if fnew > fw:
            snew = lower_bounds + np.random.random(lower_bounds.shape[0]) * (
                upper_bounds - lower_bounds
            )
            fnew = evaluate_point(snew)
            icall += 1

    return snew, fnew, icall


@numba.jit(nopython=True, cache=True)
def _compute_normalized_geometric_range(
    population: np.ndarray,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
) -> float:
    """
    Compute normalized geometric mean of parameter ranges.

    gnrng = exp(mean(log((max(x) - min(x)) / (bu - bl))))
    """
    bound = upper_bounds - lower_bounds

    # Compute max and min for each parameter (column)
    n_params = population.shape[1]
    param_ranges = np.empty(n_params)
    for i in range(n_params):
        param_ranges[i] = np.max(population[:, i]) - np.min(population[:, i])

    normalized_ranges = param_ranges / bound

    # Avoid log(0)
    for i in range(n_params):
        if normalized_ranges[i] < 1e-10:
            normalized_ranges[i] = 1e-10

    return np.exp(np.mean(np.log(normalized_ranges)))
