import math
from typing import Literal

import plotly.graph_objects as go
import polars as pl

from src import utils
from src.utils.print import format_list

from . import gr4j, sce
from .utils import Results

#########
# types #
#########

hydrological_models = {
    "GR4J": {
        "parameters": gr4j.possible_params,
    },
}

##########
# public #
##########


async def precompile() -> None:
    await gr4j.precompile_model()


def run_model(
    data: pl.DataFrame,
    hydrological_model: str,
    params: dict[str, float | int],
) -> pl.DataFrame:
    if hydrological_model.lower() == "gr4j":
        simulation = gr4j.run_model(
            data["precipitation"].to_numpy().squeeze(),
            data["evapotranspiration"].to_numpy().squeeze(),
            x1=int(params["x1"]),
            x2=params["x2"],
            x3=int(params["x3"]),
            x4=params["x4"],
        )
    else:
        raise ValueError(
            "The only available hydrological models are {}.".format(
                format_list(
                    [model.lower() for model in hydrological_models.keys()]
                )
            )
        )
    return data.with_columns(pl.Series("simulation", simulation))


def plot_simulation(
    simulation: pl.DataFrame,
    results: Results,
    objective: str,
    optimal: float,
) -> go.Figure:
    n_cols = 3
    n_rows = math.ceil((len(results["params"]) + 1) / n_cols) + 1
    x_pad = 0.1
    y_pad = 0.1
    return go.Figure(
        [
            *[
                go.Scatter(
                    x=list(range(1, len(values) + 1)),
                    y=values,
                    xaxis="x" if i == 0 else f"x{i + 1}",
                    yaxis="y" if i == 0 else f"y{i + 1}",
                    marker_color=utils.plotting.colours[0],
                    showlegend=False,
                    name=param,
                )
                for i, (param, values) in enumerate(results["params"].items())
            ],
            go.Scatter(
                x=list(range(1, len(results["objective"]) + 1)),
                y=results["objective"],
                xaxis="x5",
                yaxis="y5",
                marker_color=utils.plotting.colours[0],
                showlegend=False,
            ),
            go.Scatter(
                x=[1, len(results["objective"])],
                y=[optimal, optimal],
                xaxis="x5",
                yaxis="y5",
                mode="lines",
                line_color=utils.plotting.colours[1],
                showlegend=False,
            ),
            go.Scatter(
                x=simulation["date"],
                y=simulation["flow"],
                name="Observation",
                mode="lines",
                line_color=utils.plotting.colours[1],
                line_width=0.5,
                xaxis="x6",
                yaxis="y6",
            ),
            go.Scatter(
                x=simulation["date"],
                y=simulation["simulation"],
                name="Simulation",
                mode="lines",
                line_color=utils.plotting.colours[0],
                line_width=0.5,
                xaxis="x6",
                yaxis="y6",
            ),
        ],
        {
            "template": utils.plotting.template,
            "height": 600,
            "legend": {
                "y": 0.1,
                "yanchor": "bottom",
            },
            **{
                ("xaxis" if i == 0 else f"xaxis{i+1}"): {
                    "domain": utils.plotting.compute_domain(
                        i % n_cols, n_cols, x_pad
                    ),
                    "anchor": "y" if i == 0 else f"y{i+1}",
                }
                for i in range(len(results["params"]))
            },
            **{
                ("yaxis" if i == 0 else f"yaxis{i+1}"): {
                    "domain": utils.plotting.compute_domain(
                        i // n_cols, n_rows, y_pad, reverse=True
                    ),
                    "anchor": "x" if i == 0 else f"x{i+1}",
                }
                for i in range(len(results["params"]))
            },
            "xaxis5": {
                "domain": utils.plotting.compute_domain(1, n_cols, x_pad),
                "anchor": "y5",
            },
            "yaxis5": {
                "domain": utils.plotting.compute_domain(
                    1, n_rows, y_pad, reverse=True
                ),
                "anchor": "x5",
            },
            "xaxis6": {
                "domain": [0, 1],
                "anchor": "y6",
            },
            "yaxis6": {
                "domain": utils.plotting.compute_domain(
                    2, n_rows, y_pad, reverse=True
                ),
                "anchor": "x6",
            },
            "annotations": [
                *[
                    {
                        "showarrow": False,
                        "x": 0.5,
                        "y": 1,
                        "yref": ("y domain" if i == 0 else f"y{i + 1} domain"),
                        "xref": ("x domain" if i == 0 else f"x{i + 1} domain"),
                        "yshift": 20,
                        "text": param,
                    }
                    for i, param in enumerate(results["params"].keys())
                ],
                {
                    "showarrow": False,
                    "x": 0.5,
                    "y": 1,
                    "yref": "y5 domain",
                    "xref": "x5 domain",
                    "yshift": 20,
                    "text": objective,
                },
                {
                    "showarrow": False,
                    "x": 1,
                    "y": optimal,
                    "yref": "y5",
                    "xref": "x5 domain",
                    "xanchor": "left",
                    "text": "Optimal value",
                },
            ],
        },
    )


def calibrate_model(
    data: pl.DataFrame,
    hydrological_model: str,
    criteria: Literal["rmse", "nse", "kge"],
    transformation: Literal["log", "sqrt", "none"],
    ngs: int,
    npg: int,
    mings: int,
    nspl: int,
    maxn: int,
    kstop: int,
    pcento: float,
    peps: float,
) -> Results:
    if hydrological_model.lower() == "gr4j":
        model = gr4j.run_model
        params = gr4j.possible_params
        return sce.run_sce_calibration(
            model,
            data,
            params,
            criteria,
            transformation,
            ngs,
            npg,
            mings,
            nspl,
            maxn,
            kstop,
            pcento,
            peps,
        )
    else:
        raise ValueError(
            "The only available hydrological models are {}.".format(
                format_list(
                    [model.lower() for model in hydrological_models.keys()]
                )
            )
        )
