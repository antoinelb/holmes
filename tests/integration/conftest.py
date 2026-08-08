"""Integration fixtures: the full Starlette app over a TestClient, with the
data loaders monkeypatched to synthetic frames but the real holmes_rs models
running on them."""

from typing import Any, Iterator

import polars as pl
import pytest
from starlette.testclient import TestClient

import holmes.api
import holmes.data.hydro
import holmes.data.projection
import holmes.data.weather
import holmes.experiment
from holmes.app import create_app

from tests.unit.conftest import (  # noqa: F401  (autouse re-registration)
    _reset_api_state,
    no_network,
    tmp_data_dir,
)


@pytest.fixture
def synthetic_world(
    monkeypatch,
    stations_df: pl.DataFrame,
    weather_df: pl.DataFrame,
    grid_df: pl.DataFrame,
    streamflow_df: pl.DataFrame,
    joined_df: pl.DataFrame,
    projection_df: pl.DataFrame,
) -> None:
    async def get_station_data(**kwargs) -> pl.DataFrame:
        return stations_df

    async def get_streamflow_data(id: str) -> pl.DataFrame:
        return streamflow_df.filter(pl.col("id") == id)

    def read_weather_data(stations, **kwargs) -> pl.DataFrame:
        return weather_df

    def read_weather_grid(stations, **kwargs) -> pl.DataFrame:
        return grid_df

    async def read_data(**kwargs) -> pl.DataFrame:
        return joined_df

    def has_projection_data(stations) -> bool:
        return True

    async def read_projection_data(stations, **kwargs) -> pl.DataFrame:
        return projection_df.filter(
            pl.col("id").is_in(stations["id"].implode())
        )

    monkeypatch.setattr(
        holmes.data.hydro, "get_station_data", get_station_data
    )
    monkeypatch.setattr(
        holmes.data.hydro, "get_streamflow_data", get_streamflow_data
    )
    monkeypatch.setattr(
        holmes.data.weather, "read_weather_data", read_weather_data
    )
    monkeypatch.setattr(
        holmes.data.weather, "read_weather_grid", read_weather_grid
    )
    monkeypatch.setattr(holmes.experiment, "read_data", read_data)
    monkeypatch.setattr(
        holmes.data.projection, "has_projection_data", has_projection_data
    )
    monkeypatch.setattr(
        holmes.data.projection, "read_projection_data", read_projection_data
    )


@pytest.fixture
def client(synthetic_world) -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def recv_until(ws, type_: str, *, limit: int = 500) -> dict[str, Any]:
    """Read frames until one of the wanted type arrives; the limit guards
    against an infinite loop when the server never sends it."""
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["type"] == type_:
            return msg
    raise AssertionError(f"No {type_} message within {limit} frames")
