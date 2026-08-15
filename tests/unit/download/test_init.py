import polars as pl
import pytest

import holmes.download

expected_order = [
    "build_station_data",
    "fetch_streamflow",
    "update_era5",
    "update_ministry_grid",
    "update_stations_backfill",
    "rebuild_completed_stations",
    "rebuild_nearest_stations",
    "rebuild_grids",
    "build_projection_data",
    "build_joined_data",
]


@pytest.fixture
def download_world(monkeypatch, stations_df: pl.DataFrame):
    calls: list[tuple[str, tuple, dict]] = []

    def record(name: str, returns=None):
        def _record(*args, **kwargs):
            calls.append((name, args, kwargs))
            return returns

        return _record

    monkeypatch.setattr(
        holmes.download.hydro,
        "build_station_data",
        record("build_station_data", stations_df),
    )
    monkeypatch.setattr(
        holmes.download.hydro, "fetch_streamflow", record("fetch_streamflow")
    )
    for name in (
        "update_era5",
        "update_ministry_grid",
        "update_stations_backfill",
        "rebuild_completed_stations",
        "rebuild_nearest_stations",
        "rebuild_grids",
    ):
        monkeypatch.setattr(holmes.download.weather, name, record(name))
    monkeypatch.setattr(
        holmes.download.projection,
        "build_projection_data",
        record("build_projection_data"),
    )
    monkeypatch.setattr(
        holmes.download.joined,
        "build_joined_data",
        record("build_joined_data"),
    )
    return calls


class TestRunDownload:
    def test_runs_every_step_in_order(self, download_world, stations_df):
        holmes.download.run_download()

        assert [name for name, _, _ in download_world] == expected_order

        by_name = {
            name: (args, kwargs) for name, args, kwargs in download_world
        }
        # the station frame built first is the one threaded through
        for name in (
            "fetch_streamflow",
            "update_era5",
            "update_ministry_grid",
            "build_projection_data",
            "rebuild_nearest_stations",
            "rebuild_grids",
            "build_joined_data",
        ):
            args, _ = by_name[name]
            assert len(args) == 1
            assert args[0] is stations_df
        for name in (
            "build_station_data",
            "update_stations_backfill",
            "rebuild_completed_stations",
        ):
            args, _ = by_name[name]
            assert args == ()

        forced = {
            name: kwargs["force"]
            for name, _, kwargs in download_world
            if "force" in kwargs
        }
        assert forced == {
            "build_station_data": False,
            "fetch_streamflow": False,
            "update_era5": False,
            "update_ministry_grid": False,
            "update_stations_backfill": False,
            "build_projection_data": False,
        }
        for name in (
            "rebuild_completed_stations",
            "rebuild_nearest_stations",
            "rebuild_grids",
            "build_joined_data",
        ):
            _, kwargs = by_name[name]
            assert kwargs == {}

    def test_force_reaches_every_incremental_step(self, download_world):
        holmes.download.run_download(force=True)

        assert [name for name, _, _ in download_world] == expected_order
        forced = [
            kwargs["force"]
            for _, _, kwargs in download_world
            if "force" in kwargs
        ]
        assert forced == [True] * 6
