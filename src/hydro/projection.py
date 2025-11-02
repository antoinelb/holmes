from datetime import datetime, timedelta
from typing import cast

import plotly.graph_objects as go
import polars as pl

from src import utils
from src.data import read_cemaneige_info, read_projection_data

from .hydro import run_model
from .oudin import run_oudin
from .snow import run_snow_model

##########
# public #
##########


def run_projection(
    config: dict[str, str | dict[str, float]],
    climate_model: str,
    climate_scenario: str,
    horizon: str,
):
    data = read_projection_data(
        config["catchment"],  # type: ignore
        climate_model,
        climate_scenario,
        horizon,
    )

    # date column and precipitation and temperature per member
    n_members = (data.shape[1] - 1) // 2

    _projections = [
        _run_projection(
            data.select(
                "date",
                pl.col(f"member_{i+1}_temperature").alias("temperature"),
                pl.col(f"member_{i+1}_precipitation").alias("precipitation"),
            ),
            config,
        ).rename({"flow": f"member_{i+1}_flow"})
        for i in range(n_members)
    ]
    return pl.concat(
        [
            projection if i == 0 else projection.drop("date")
            for i, projection in enumerate(_projections)
        ],
        how="horizontal",
    )


def plot_projection(
    data: pl.DataFrame,
    config: dict[str, str | dict[str, float]],
    climate_model: str,
    climate_scenario: str,
    horizon: str,
    multimodel: bool,
) -> go.Figure:
    median = (
        data.unpivot(
            index="date",
        )
        .group_by("date")
        .agg(pl.col("value").median().alias("median_flow"))
        .sort("date")
    )
    return go.Figure(
        [
            *[
                go.Scatter(
                    x=data["date"],
                    y=data[f"member_{i+1}_flow"],
                    name="Members",
                    mode="lines",
                    line_width=0.5,
                    line_color=utils.plotting.colours[0],
                    showlegend=i == 0,
                )
                for i in range(data.shape[1] - 1)
            ],
            go.Scatter(
                x=median["date"],
                y=median["median_flow"],
                name="Median",
                mode="lines",
                line_width=2,
                line_color=utils.plotting.colours[0],
            ),
        ],
        {
            "template": utils.plotting.template,
            "title": "{}, (Climate Model: {}, Scenario: {}, Horizon: {})".format(
                config["catchment"],
                climate_model,
                climate_scenario,
                horizon.replace("H", ""),
            ),
            "legend": {
                "xanchor": "right",
            },
            "height": 600,
            "xaxis": {
                "title": "Months",
                "tickformat": "%b",
                "dtick": "M1",
            },
            "yaxis": {
                "title": "Mean interannual daily flow [mm]",
            },
        },
    )


###########
# private #
###########


def _run_projection(
    data: pl.DataFrame, config: dict[str, str | dict[str, float]]
) -> pl.DataFrame:
    lat = read_cemaneige_info(cast(str, config["catchment"]))["latitude"]
    temperature = data["temperature"].to_numpy().squeeze()
    day_of_year = (
        data.select(pl.col("date").dt.ordinal_day()).to_numpy().squeeze()
    )
    evapotranspiration = run_oudin(temperature, day_of_year, lat)
    precipitation = run_snow_model(
        data, config["snow_model"].lower(), config["catchment"]  # type: ignore
    )

    flow = run_model(
        data.select("date").with_columns(
            pl.Series("precipitation", precipitation),
            pl.Series("evapotranspiration", evapotranspiration),
        ),
        config["hydrological_model"],  # type: ignore
        {param["name"]: param["value"] for param in config["params"]},  # type: ignore
    )
    data = data.select("date").with_columns(pl.Series("flow", flow))

    data = (
        data.with_columns(
            pl.col("date")
            .dt.replace(day=28)
            .dt.replace(year=pl.col("date").dt.year().max())
        )
        .group_by("date")
        .agg(pl.col("flow").mean())
        .sort("date")
    )

    return data
