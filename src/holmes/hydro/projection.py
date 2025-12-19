import plotly.graph_objects as go
import polars as pl

from holmes import utils
from holmes.data import read_cemaneige_info, read_projection_data

from .hydro import run_model
from .oudin import run_oudin
from .snow import run_snow_model

##########
# public #
##########


def run_projection(
    hydrological_model: str,
    catchment: str,
    snow_model: str,
    params: dict[str, float],
    climate_model: str,
    climate_scenario: str,
    horizon: str,
):
    data = read_projection_data(
        catchment, climate_model, climate_scenario, horizon
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
            hydrological_model,
            catchment,
            snow_model,
            params,
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
    catchment: str,
    climate_model: str,
    climate_scenario: str,
    horizon: str,
    *,
    template: str | dict[str, go.Layout] | None = None,
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
            "template": (
                utils.plotting.template if template is None else template
            ),
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "title": "{}, (Climate Model: {}, Scenario: {}, Horizon: {})".format(
                catchment,
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
    data: pl.DataFrame,
    hydrological_model: str,
    catchment: str,
    snow_model: str,
    params: dict[str, float],
) -> pl.DataFrame:
    lat = read_cemaneige_info(catchment)["latitude"]
    temperature = data["temperature"].to_numpy().squeeze()
    day_of_year = (
        data.select(pl.col("date").dt.ordinal_day()).to_numpy().squeeze()
    )
    evapotranspiration = run_oudin(temperature, day_of_year, lat)
    precipitation = run_snow_model(
        data, snow_model.lower(), catchment  # type: ignore
    )

    flow = run_model(
        data.select("date").with_columns(
            pl.Series("precipitation", precipitation),
            pl.Series("evapotranspiration", evapotranspiration),
        ),
        hydrological_model,
        params,
    )
    data = data.select("date").with_columns(pl.Series("flow", flow))

    data = (
        data.filter(
            ~(
                (pl.col("date").dt.month() == 2)
                & (pl.col("date").dt.day() == 29)
            )
        )
        .with_columns(
            pl.col("date").dt.replace(year=pl.col("date").dt.year().max())
        )
        .group_by("date")
        .agg(pl.col("flow").mean())
        .sort("date")
    )

    return data
