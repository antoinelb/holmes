from pathlib import Path

import altair as alt
import polars as pl

from holmes.utils.plotting import colours

##########
# public #
##########


def write_missing_fig(data: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(exist_ok=True, parents=True)

    missing_fig = alt.vconcat(
        _create_missing_fig(data, "mm", "streamflow"),
        _create_missing_fig(data, "mm", "precipitation"),
        _create_missing_fig(data, "°C", "temperature"),
    ).properties(title=f"{data[0, 'name']} ({data[0, 'id']})")
    missing_fig.save(path)


###########
# private #
###########


def _create_missing_fig(
    data: pl.DataFrame, units: str, variable: str
) -> alt.typing.ChartType:
    width = 600
    height = 200

    data = data.select("datetime", variable).with_columns(
        pl.col(variable).is_null().alias("missing")
    )

    lines = (
        alt.Chart(data)
        .mark_line(color=colours[0], size=1)
        .encode(
            x=alt.X("datetime:T", axis=alt.Axis(title="")),
            y=alt.Y(
                f"{variable}:Q", axis=alt.Axis(title=f"{variable} ({units})")
            ),
        )
    )

    # Collapse consecutive missing days into runs so each gap is one rect
    # instead of one rule per day (which reads as vertical striping).
    missing_runs = (
        data.filter(pl.col("missing"))
        .with_columns(
            (pl.col("datetime").diff().dt.total_days().fill_null(1) > 1)
            .cum_sum()
            .alias("run")
        )
        .group_by("run")
        .agg(
            start=pl.col("datetime").min(),
            end=pl.col("datetime").max(),
        )
    )

    missing_lines = (
        alt.Chart(missing_runs)
        .mark_rect(color=colours[1], opacity=0.15)
        .encode(x="start:T", x2="end:T")
    )

    return alt.layer(lines, missing_lines).properties(
        height=height,
        width=width,
    )
