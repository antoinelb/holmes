import numpy as np
import plotly.graph_objects as go
import polars as pl

from src import utils

from .utils import evaluate_simulation, get_optimal_for_criteria

##########
# public #
##########


def plot_simulation(data: pl.DataFrame) -> go.Figure:
    n_cols = 3
    n_rows = 3
    x_pad = 0.15
    y_pad = 0.15

    results = _evaluate_simulations(data)

    return go.Figure(
        [
            *[
                go.Bar(
                    x=[f"simulation {j+1}" for j in range(len(values))],
                    y=values,
                    showlegend=False,
                    name=f"Simulation {i+1}",
                    xaxis="x" if i == 0 else f"x{i+1}",
                    yaxis="y" if i == 0 else f"y{i+1}",
                    marker_color=utils.plotting.colours[: len(values)],
                )
                for i, (metric, (values, _)) in enumerate(results.items())
            ],
            go.Scatter(
                x=data["date"],
                y=data["flow"],
                name="Observations",
                xaxis="x7",
                yaxis="y7",
            ),
            *[
                go.Scatter(
                    x=data["date"],
                    y=data[f"simulation_{i+1}"],
                    name=f"Simulation {i+1}",
                    xaxis="x7",
                    yaxis="y7",
                    # line_width=0.5,
                    line_color=utils.plotting.colours[
                        i % len(utils.plotting.colours)
                    ],
                )
                for i in range(
                    data.drop(
                        "date", "flow", "multimodel", strict=False
                    ).shape[1]
                )
            ],
            *(
                [
                    go.Scatter(
                        x=data["date"],
                        y=data["multimodel"],
                        name="Multimodel",
                        xaxis="x7",
                        yaxis="y7",
                        line_color="rgb(92,17,160)",
                    )
                ]
                if "multimodel" in data.columns
                else []
            ),
        ],
        {
            "template": utils.plotting.template,
            "height": 600,
            "legend": {
                "y": 0.1,
                "yanchor": "bottom",
            },
            "shapes": [
                {
                    "type": "line",
                    "x0": 0,
                    "x1": 1,
                    "xref": ("x" if i == 0 else f"x{i+1}") + " domain",
                    "y0": optimal,
                    "y1": optimal,
                    "yref": "y" if i == 0 else f"y{i+1}",
                    "line_color": "red",
                }
                for i, (metric, (values, optimal)) in enumerate(
                    results.items()
                )
            ],
            "annotations": [
                {
                    "showarrow": False,
                    "x": 1,
                    "y": 1,
                    "xref": "x3 domain",
                    "yref": "y3",
                    "xanchor": "left",
                    "text": "Optimal",
                    "font_color": "red",
                },
            ],
            **{
                ("xaxis" if i == 0 else f"xaxis{i+1}"): {
                    "domain": utils.plotting.compute_domain(
                        i % n_cols, n_cols, x_pad
                    ),
                    "anchor": "y" if i == 0 else f"y{i+1}",
                }
                for i in range(6)
            },
            **{
                ("yaxis" if i == 0 else f"yaxis{i+1}"): {
                    "domain": utils.plotting.compute_domain(
                        i // n_cols,
                        n_rows + 1,  # the last plot takes height of two plots
                        y_pad,
                        reverse=True,
                    ),
                    "anchor": "x" if i == 0 else f"x{i+1}",
                    "title": [
                        "High flows<br>(NSE)",
                        "Medium flows<br>(NSE-sqrt)",
                        "Low flows<br>(NSE-log)",
                        "Water balance<br>(Mean bias)",
                        "Flow variability<br>(Deviation bias)",
                        "Correlation",
                    ][i],
                    "title_font_size": 12,
                }
                for i in range(6)
            },
            "xaxis7": {"domain": [0, 1], "anchor": "y7", "title": "Date"},
            "yaxis7": {
                "domain": [
                    0,
                    utils.plotting.compute_domain(
                        2, n_rows + 1, y_pad, reverse=True
                    )[1],
                ],  # the last plot takes the height of two plots
                "anchor": "x7",
                "title": "Streamflow [mm/D]",
            },
        },
    )


###########
# private #
###########


def _evaluate_simulations(
    data: pl.DataFrame,
) -> dict[str, tuple[list[float], float]]:
    results = [
        _evaluate_simulation(
            data["flow"].to_numpy().squeeze(),
            data[f"simulation_{i+1}"].to_numpy().squeeze(),
        )
        for i in range(
            data.drop("date", "flow", "multimodel", strict=False).shape[1]
        )
    ]
    return {
        "nse_high": (
            [result["nse_high"] for result in results],
            get_optimal_for_criteria("nse"),
        ),
        "nse_medium": (
            [result["nse_medium"] for result in results],
            get_optimal_for_criteria("nse"),
        ),
        "nse_low": (
            [result["nse_low"] for result in results],
            get_optimal_for_criteria("nse"),
        ),
        "water_balance": (
            [result["water_balance"] for result in results],
            get_optimal_for_criteria("mean_bias"),
        ),
        "flow_variability": (
            [result["flow_variability"] for result in results],
            get_optimal_for_criteria("deviation_bias"),
        ),
        "correlation": (
            [result["correlation"] for result in results],
            get_optimal_for_criteria("correlation"),
        ),
    }


def _evaluate_simulation(
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
