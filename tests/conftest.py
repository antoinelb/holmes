"""Shared synthetic data for unit and integration tests.

Only lazy (non-autouse) fixtures belong here: this conftest is also in scope
for the e2e suite, which must keep real network access and the real data
directory.
"""

import io
import zipfile
from datetime import date
from typing import Any

import numpy as np
import polars as pl
import pytest
import shapely

station_ids = ["061004", "061020"]

weather_start = date(2015, 1, 1)
weather_end = date(2017, 12, 31)


@pytest.fixture(scope="session")
def stations_df() -> pl.DataFrame:
    rows = []
    for i, id in enumerate(station_ids):
        lat = 47.7 + 0.5 * i
        lon = -71.3 + 0.5 * i
        polygon = shapely.box(lon - 0.15, lat - 0.15, lon + 0.15, lat + 0.15)
        rows.append(
            {
                "id": id,
                "name": f"Station {id}",
                "type": "Débit",
                "lat": lat,
                "lon": lon,
                "start": 2015,
                "end": 2017,
                "waterway": "Rivière",
                "area": 500.0,
                "open": True,
                "geometry": shapely.to_wkb(polygon),
                "elevation_layers": [300.0, 400.0, 500.0, 600.0, 700.0],
            }
        )
    return pl.DataFrame(
        rows,
        schema={
            "id": pl.String,
            "name": pl.String,
            "type": pl.String,
            "lat": pl.Float64,
            "lon": pl.Float64,
            "start": pl.Int64,
            "end": pl.Int64,
            "waterway": pl.String,
            "area": pl.Float64,
            "open": pl.Boolean,
            "geometry": pl.Binary,
            "elevation_layers": pl.List(pl.Float64),
        },
    )


@pytest.fixture(scope="session")
def weather_df() -> pl.DataFrame:
    return make_forcing(station_ids, weather_start, weather_end).with_columns(
        pl.col("datetime").cast(pl.Datetime("us"))
    )


@pytest.fixture(scope="session")
def grid_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": station_ids,
            "latitude": [47.7, 48.2],
            "longitude": [-71.3, -70.8],
            "weight": [1.0, 1.0],
            "geometry": [None, None],
            "climate_id": [None, None],
            "name": [None, None],
            "start": [None, None],
            "end": [None, None],
        },
        schema={
            "id": pl.String,
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "weight": pl.Float64,
            "geometry": pl.String,
            "climate_id": pl.String,
            "name": pl.String,
            "start": pl.Date,
            "end": pl.Date,
        },
    )


@pytest.fixture(scope="session")
def streamflow_df() -> pl.DataFrame:
    frames = [
        make_streamflow(id, weather_start, weather_end) for id in station_ids
    ]
    return pl.concat(frames)


@pytest.fixture(scope="session")
def joined_df(
    stations_df: pl.DataFrame,
    weather_df: pl.DataFrame,
    streamflow_df: pl.DataFrame,
) -> pl.DataFrame:
    # mirrors the join in holmes.experiment.read_data
    weather = weather_df.with_columns(pl.col("datetime").dt.date())
    return (
        stations_df.select(
            "id", "name", "lat", "lon", "area", "elevation_layers"
        )
        .join(
            weather.join(streamflow_df, on=["id", "datetime"], how="left"),
            on="id",
        )
        .fill_nan(None)
    )


@pytest.fixture(scope="session")
def projection_df() -> pl.DataFrame:
    frames = []
    for id in station_ids:
        for member in ["historical-r1-r1i1p1", "historical-r2-r2i1p1"]:
            frames.append(
                make_forcing([id], date(2020, 1, 1), date(2049, 12, 31))
                .with_columns(
                    pl.lit("ClimEx").alias("ensemble"),
                    pl.lit("rcp8.5").alias("scenario"),
                    pl.lit(member).alias("member"),
                )
                .select(
                    "id",
                    "ensemble",
                    "scenario",
                    "member",
                    "datetime",
                    "precipitation",
                    "temperature",
                )
            )
    return pl.concat(frames).sort(
        "id", "ensemble", "scenario", "member", "datetime"
    )


@pytest.fixture
def ipc_bytes():
    def _ipc_bytes(data: pl.DataFrame) -> bytes:
        buffer = io.BytesIO()
        data.write_ipc(buffer)
        return buffer.getvalue()

    return _ipc_bytes


@pytest.fixture
def zip_bytes():
    def _zip_bytes(files: dict[str, pl.DataFrame | bytes]) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in files.items():
                if isinstance(content, pl.DataFrame):
                    inner = io.BytesIO()
                    content.write_ipc(inner)
                    content = inner.getvalue()
                archive.writestr(name, content)
        return buffer.getvalue()

    return _zip_bytes


@pytest.fixture
def release_json():
    def _release_json(
        date_str: str, extra_assets: list[str] | None = None
    ) -> dict[str, Any]:
        names = [f"data-{date_str}.zip", *(extra_assets or [])]
        return {
            "tag_name": "data",
            "assets": [
                {
                    "name": name,
                    "browser_download_url": f"https://example.com/{name}",
                }
                for name in names
            ],
        }

    return _release_json


def make_forcing(ids: list[str], start: date, end: date) -> pl.DataFrame:
    """Deterministic daily forcing: sinusoidal temperature (−15 °C winter to
    +22 °C summer, so cemaneige sees snow) and gamma precipitation."""
    days = pl.date_range(start, end, eager=True).alias("datetime")
    doy = days.dt.ordinal_day().to_numpy()
    rng = np.random.default_rng(0)
    frames = []
    for i, id in enumerate(ids):
        temperature = (
            3.5
            - 18.5 * np.cos(2 * np.pi * doy / 365.25)
            + rng.normal(0, 2, len(days))
            + i
        )
        precipitation = rng.gamma(0.5, 6.0, len(days))
        frames.append(
            pl.DataFrame(
                {
                    "id": np.full(len(days), id),
                    "datetime": days,
                    "precipitation": precipitation,
                    "temperature": temperature,
                }
            )
        )
    return pl.concat(frames)


def make_streamflow(id: str, start: date, end: date) -> pl.DataFrame:
    days = pl.date_range(start, end, eager=True).alias("datetime")
    doy = days.dt.ordinal_day().to_numpy()
    rng = np.random.default_rng(1)
    streamflow = (
        1.5
        + 1.2 * np.sin(2 * np.pi * (doy - 120) / 365.25)
        + rng.gamma(0.5, 0.4, len(days))
    )
    return pl.DataFrame(
        {
            "id": np.full(len(days), id),
            "datetime": days,
            "streamflow": streamflow,
        }
    )
