import zipfile
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import geopandas as gpd
import numpy as np
import polars as pl
import pytest
import shapely
import xarray as xr

import holmes.download.weather as weather
from holmes.data.archive import MissingDataError

crs = "EPSG:32198"

station_locations = {
    "7060225": (47.7, -71.3),
    "7061439": (47.75, -71.25),
    "7066573": (47.8, -71.2),
    "7066611": (48.1, -70.9),
    "7066820": (48.2, -70.8),
}


@pytest.fixture
def polygons(stations_df: pl.DataFrame) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "id": stations_df["id"].to_list(),
            "geometry": [
                shapely.from_wkb(wkb) for wkb in stations_df["geometry"]
            ],
        },
        crs="EPSG:4326",
    ).to_crs(crs)


@pytest.fixture
def empty_polygons() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"id": [], "geometry": gpd.GeoSeries([], crs="EPSG:4326")}
    ).to_crs(crs)


@pytest.fixture
def station_csvs(tmp_data_dir: Path) -> None:
    for climate_id, (name, _) in weather.stations_files.items():
        lat, lon = station_locations[climate_id]
        path = tmp_data_dir / "raw" / name
        path.parent.mkdir(exist_ok=True, parents=True)
        # the record opens with an unobserved day, so the inventory span
        # must start on the first day carrying any value
        path.write_text(
            "datetime,lat,lon,precipitation,tmax,tmin,temperature\n"
            f"2015-01-01,{lat},{lon},,,,\n"
            f"2015-01-02,{lat},{lon},1.0,2.0,-2.0,0.0\n"
            f"2015-01-03,{lat},{lon},2.0,3.0,-1.0,1.0\n"
            f"2015-01-04,{lat},{lon},,4.0,0.0,2.0\n"
        )


@pytest.fixture
def backfill_product(tmp_data_dir: Path) -> pl.DataFrame:
    days = pl.datetime_range(
        datetime(2015, 1, 1), datetime(2015, 1, 6), interval="1d", eager=True
    ).alias("datetime")
    backfill = pl.concat(
        [
            pl.DataFrame(
                {
                    "climate_id": np.full(len(days), climate_id),
                    "datetime": days,
                    "precipitation": np.full(len(days), 9.0),
                    "temperature": np.full(len(days), -9.0),
                }
            )
            for climate_id in weather.stations_files
        ]
    )
    path = tmp_data_dir / "raw" / weather.stations_backfill_file
    path.parent.mkdir(exist_ok=True, parents=True)
    backfill.write_ipc(path)
    return backfill


def make_ministry_dataset(
    polygons: gpd.GeoDataFrame, year: int, days: int = 3
) -> xr.Dataset:
    min_x, min_y, max_x, max_y = polygons.total_bounds
    xs = np.linspace(min_x - 5000, max_x + 5000, 6)
    ys = np.linspace(min_y - 5000, max_y + 5000, 6)
    time = np.array(
        [
            np.datetime64(f"{year}-01-{day + 1:02d}T05:00", "ns")
            for day in range(days)
        ]
    )
    return xr.Dataset(
        {
            "PREC": (("time", "y", "x"), np.full((days, 6, 6), 2.0)),
            "TMOY": (("time", "y", "x"), np.full((days, 6, 6), -3.0)),
        },
        coords={"time": time, "y": ys, "x": xs},
    )


def make_processed_dataset(
    polygons: gpd.GeoDataFrame, year: int, days: int = 3
) -> xr.Dataset:
    data = make_ministry_dataset(polygons, year, days).rename(
        {"PREC": "precipitation", "TMOY": "temperature"}
    )
    data = data.rio.set_spatial_dims(x_dim="x", y_dim="y")
    return data.rio.write_crs(crs)


def make_response(content: bytes) -> MagicMock:
    # doubles as its own context manager, since the grids are streamed
    resp = MagicMock()
    resp.content = content
    resp.iter_bytes.return_value = [content]
    resp.__enter__.return_value = resp
    return resp


def make_hourly(start: datetime, end: datetime) -> pl.DataFrame:
    hours = pl.datetime_range(start, end, interval="1h", eager=True)
    return pl.DataFrame(
        {
            "valid_time": hours.dt.strftime("%Y-%m-%d %H:%M:%S"),
            "tp": np.full(len(hours), 0.001),
            "t2m": np.full(len(hours), 273.15),
        }
    )


def make_product(ids: list[str], years: list[int]) -> pl.DataFrame:
    days = [datetime(year, month, 1) for year in years for month in (1, 7, 12)]
    return pl.DataFrame(
        {
            "id": [id_ for id_ in ids for _ in days],
            "datetime": days * len(ids),
            "precipitation": [111.0] * len(days) * len(ids),
            "temperature": [-111.0] * len(days) * len(ids),
        },
        schema={
            "id": pl.String,
            "datetime": pl.Datetime("us"),
            "precipitation": pl.Float64,
            "temperature": pl.Float64,
        },
    ).sort("id", "datetime")


def no_part_files(tmp_data_dir: Path) -> bool:
    return not list(tmp_data_dir.rglob("*.part"))


class TestUpdateEra5:
    def test_cold_build_writes_product_and_cell_files(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        monkeypatch.setattr(weather.cdsapi, "Client", MagicMock())
        spans: list[tuple[int, int]] = []

        def fake_range(latitude, longitude, start, end):
            spans.append((start, end))
            return make_hourly(
                datetime(start, 1, 1), datetime(end, 12, 31, 23)
            )

        monkeypatch.setattr(weather, "_download_era5_cell_range", fake_range)
        weather.update_era5(stations_df.head(1))

        assert all(span == (2015, 2017) for span in spans)
        product = pl.read_ipc(
            tmp_data_dir / "raw" / "weather" / "era5.ipc", memory_map=False
        )
        assert product["id"].unique().to_list() == ["061004"]
        # the leading partial local day from the UTC shift is not written
        assert product["datetime"].min() == datetime(2015, 1, 1)
        interior = product.filter(pl.col("datetime") == datetime(2015, 7, 1))
        assert interior["precipitation"][0] == pytest.approx(24.0)
        assert interior["temperature"][0] == pytest.approx(0.0)
        cell_files = sorted(
            (tmp_data_dir / "raw" / "weather" / "era5").glob("*.ipc")
        )
        years = {file.stem.split("_")[2] for file in cell_files}
        assert years == {"2015", "2016", "2017"}
        assert all(len(file.stem.split("_")) == 3 for file in cell_files)
        assert no_part_files(tmp_data_dir)

    def test_incremental_upserts_refresh_years(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        monkeypatch.setattr(weather.cdsapi, "Client", MagicMock())
        monkeypatch.setattr(weather, "_years_to_refresh", lambda today: [2025])
        old = make_product(["061004", "061020"], [2023, 2024])
        path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        path.parent.mkdir(exist_ok=True, parents=True)
        old.write_ipc(path)

        era5_dir = tmp_data_dir / "raw" / "weather" / "era5"
        era5_dir.mkdir(exist_ok=True, parents=True)
        legacy = era5_dir / "47.75_-71.25_1940_2024.ipc"
        legacy.write_bytes(b"legacy")
        # a stale refresh-year cell file must be dropped and refetched
        stale = era5_dir / "47.75_-71.25_2025.ipc"
        pl.DataFrame(
            {
                "datetime": [datetime(2025, 1, 1)],
                "precipitation": [999.0],
                "temperature": [999.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        ).write_ipc(stale)

        def fake_range(latitude, longitude, start, end):
            assert (start, end) == (2025, 2025)
            return make_hourly(datetime(2025, 1, 1), datetime(2025, 2, 1, 23))

        monkeypatch.setattr(weather, "_download_era5_cell_range", fake_range)
        weather.update_era5(stations_df)

        product = pl.read_ipc(path, memory_map=False)
        cutoff = datetime(2025, 1, 1)
        assert product.filter(pl.col("datetime") < cutoff).equals(old)
        new_rows = product.filter(pl.col("datetime") >= cutoff)
        assert sorted(new_rows["id"].unique()) == ["061004", "061020"]
        assert new_rows.filter(pl.col("datetime") == datetime(2025, 1, 15))[
            "precipitation"
        ].to_list() == pytest.approx([24.0, 24.0])
        assert not legacy.exists()
        refetched = pl.read_ipc(stale, memory_map=False)
        assert 999.0 not in refetched["precipitation"].to_list()
        assert no_part_files(tmp_data_dir)

    def test_force_selects_full_build(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        old = make_product(["061004"], [2023])
        path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        path.parent.mkdir(exist_ok=True, parents=True)
        old.write_ipc(path)

        grid = pl.DataFrame(
            {
                "id": ["061004"],
                "latitude": [47.75],
                "longitude": [-71.25],
                "weight": [1.0],
            }
        )
        series = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        )
        ensure = MagicMock(return_value=0)
        monkeypatch.setattr(weather, "_era5_grid", lambda polygons: grid)
        monkeypatch.setattr(weather, "_ensure_era5_cells", ensure)
        monkeypatch.setattr(
            weather, "_read_era5_years", lambda cells, years: series
        )
        weather.update_era5(stations_df, force=True)

        # the full span is fetched without dropping cached files
        assert ensure.call_args.args[1] == [2015, 2016, 2017]
        assert ensure.call_args.kwargs == {"refetch": False}
        product = pl.read_ipc(path, memory_map=False)
        # the old product is replaced outright, not upserted
        assert product["datetime"].to_list() == [datetime(2015, 1, 1)]


class TestUpdateMinistryGrid:
    @pytest.fixture
    def era5_product(self, tmp_data_dir, weather_df) -> pl.DataFrame:
        path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        path.parent.mkdir(exist_ok=True, parents=True)
        weather_df.write_ipc(path)
        return weather_df

    def test_missing_era5_product_raises(self, tmp_data_dir, stations_df):
        with pytest.raises(MissingDataError, match="update_era5"):
            weather.update_ministry_grid(stations_df)

    def test_full_build(
        self, tmp_data_dir, monkeypatch, stations_df, era5_product, polygons
    ):
        processed = make_processed_dataset(polygons, 2015)
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year: processed if year == 2015 else None,
        )
        weather.update_ministry_grid(stations_df)

        product = pl.read_ipc(
            tmp_data_dir / "raw" / "weather" / "ministry_grid.ipc",
            memory_map=False,
        )
        assert sorted(product["id"].unique()) == ["061004", "061020"]
        # constant field: the coverage-weighted mean is the constant
        assert product["precipitation"].to_list() == pytest.approx([2.0] * 6)
        assert product["temperature"].to_list() == pytest.approx([-3.0] * 6)
        assert no_part_files(tmp_data_dir)

    def test_force_selects_full_build(
        self, tmp_data_dir, monkeypatch, stations_df, era5_product, polygons
    ):
        old = make_product(["061004", "061020"], [2014])
        path = tmp_data_dir / "raw" / "weather" / "ministry_grid.ipc"
        path.parent.mkdir(exist_ok=True, parents=True)
        old.write_ipc(path)

        processed = make_processed_dataset(polygons, 2015)
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year: processed if year == 2015 else None,
        )
        weather.update_ministry_grid(stations_df, force=True)

        product = pl.read_ipc(path, memory_map=False)
        # the old product is replaced outright, not upserted
        assert product["datetime"].dt.year().unique().to_list() == [2015]
        assert product["precipitation"].to_list() == pytest.approx([2.0] * 6)

    def test_incremental_refresh(
        self, tmp_data_dir, monkeypatch, stations_df, era5_product, polygons
    ):
        monkeypatch.setattr(weather, "_years_to_refresh", lambda today: [2016])
        old = make_product(["061004", "061020"], [2015, 2016])
        path = tmp_data_dir / "raw" / "weather" / "ministry_grid.ipc"
        path.parent.mkdir(exist_ok=True, parents=True)
        old.write_ipc(path)
        # the stale cached year must be dropped before the redownload
        stale = (
            tmp_data_dir / "raw" / "weather" / "ministry_grid" / "PREC_2016.nc"
        )
        stale.parent.mkdir(exist_ok=True, parents=True)
        stale.write_bytes(b"stale")

        processed = make_processed_dataset(polygons, 2016)
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year: processed if year == 2016 else None,
        )
        weather.update_ministry_grid(stations_df)

        assert not stale.exists()
        product = pl.read_ipc(path, memory_map=False)
        cutoff = datetime(2016, 1, 1)
        assert product.filter(pl.col("datetime") < cutoff).equals(
            old.filter(pl.col("datetime") < cutoff)
        )
        new_rows = product.filter(pl.col("datetime") >= cutoff)
        assert new_rows["precipitation"].to_list() == pytest.approx([2.0] * 6)

    def test_incremental_failed_year_keeps_old_rows(
        self, tmp_data_dir, monkeypatch, stations_df, era5_product
    ):
        monkeypatch.setattr(weather, "_years_to_refresh", lambda today: [2016])
        old = make_product(["061004"], [2015, 2016])
        path = tmp_data_dir / "raw" / "weather" / "ministry_grid.ipc"
        path.parent.mkdir(exist_ok=True, parents=True)
        old.write_ipc(path)

        warn = MagicMock()
        monkeypatch.setattr(weather, "warn_print", warn)
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year: None,
        )
        weather.update_ministry_grid(stations_df)

        warn.assert_called_once()
        assert pl.read_ipc(path, memory_map=False).equals(old)

    def test_incremental_partial_failure_carries_old_rows(
        self, tmp_data_dir, monkeypatch, stations_df, era5_product, polygons
    ):
        monkeypatch.setattr(
            weather, "_years_to_refresh", lambda today: [2015, 2016]
        )
        old = make_product(["061004", "061020"], [2014, 2015, 2016])
        path = tmp_data_dir / "raw" / "weather" / "ministry_grid.ipc"
        path.parent.mkdir(exist_ok=True, parents=True)
        old.write_ipc(path)

        warn = MagicMock()
        monkeypatch.setattr(weather, "warn_print", warn)
        processed = make_processed_dataset(polygons, 2015)
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year: processed if year == 2015 else None,
        )
        weather.update_ministry_grid(stations_df)

        warn.assert_called_once()
        product = pl.read_ipc(path, memory_map=False)
        # 2014 is untouched, 2015 is fresh, failed 2016 keeps its old rows
        assert product.filter(pl.col("datetime").dt.year() == 2014).equals(
            old.filter(pl.col("datetime").dt.year() == 2014)
        )
        assert product.filter(pl.col("datetime").dt.year() == 2015)[
            "precipitation"
        ].to_list() == pytest.approx([2.0] * 6)
        assert (
            product.filter(pl.col("datetime").dt.year() == 2016)
            .sort("id", "datetime")
            .equals(old.filter(pl.col("datetime").dt.year() == 2016))
        )


class TestUpdateStationsBackfill:
    @pytest.fixture
    def samples(self) -> tuple[pl.DataFrame, pl.DataFrame]:
        days = pl.datetime_range(
            datetime(2015, 1, 1),
            datetime(2015, 1, 3),
            interval="1d",
            eager=True,
        )
        ministry = pl.DataFrame(
            {
                "climate_id": ["7060225"] * 2,
                "datetime": days[:2],
                "precipitation": [1.0, None],
                "temperature": [-1.0, -2.0],
            }
        )
        era5 = pl.DataFrame(
            {
                "climate_id": ["7060225"] * 3,
                "datetime": days,
                "precipitation": [8.0, 8.0, 8.0],
                "temperature": [-8.0, -8.0, -8.0],
            }
        )
        return ministry, era5

    def test_missing_station_csv_raises(self, tmp_data_dir):
        with pytest.raises(MissingDataError, match="no public source"):
            weather.update_stations_backfill()

    def test_full_build_ministry_wins(
        self, tmp_data_dir, monkeypatch, station_csvs, samples
    ):
        ministry, era5 = samples
        sample_ministry = MagicMock(return_value=ministry)
        sample_era5 = MagicMock(return_value=era5)
        monkeypatch.setattr(weather, "_sample_ministry_grid", sample_ministry)
        monkeypatch.setattr(weather, "_sample_era5_cells", sample_era5)
        weather.update_stations_backfill()

        expected_years = list(
            range(weather.ministry_grid_start_year, date.today().year + 1)
        )
        assert sample_ministry.call_args.args[1] == expected_years
        assert sample_era5.call_args.args[1] == expected_years
        backfill = pl.read_ipc(
            tmp_data_dir / "raw" / weather.stations_backfill_file,
            memory_map=False,
        )
        assert backfill["precipitation"].to_list() == [1.0, 8.0, 8.0]
        assert backfill["temperature"].to_list() == [-1.0, -2.0, -8.0]
        assert no_part_files(tmp_data_dir)

    def test_force_selects_full_build(
        self, tmp_data_dir, monkeypatch, station_csvs, samples
    ):
        ministry, era5 = samples
        old = pl.DataFrame(
            {
                "climate_id": ["7060225"],
                "datetime": [datetime(2014, 7, 1)],
                "precipitation": [5.0],
                "temperature": [-5.0],
            }
        )
        path = tmp_data_dir / "raw" / weather.stations_backfill_file
        path.parent.mkdir(exist_ok=True, parents=True)
        old.write_ipc(path)

        monkeypatch.setattr(
            weather, "_sample_ministry_grid", lambda inv, years: ministry
        )
        monkeypatch.setattr(
            weather, "_sample_era5_cells", lambda inv, years: era5
        )
        weather.update_stations_backfill(force=True)

        backfill = pl.read_ipc(path, memory_map=False)
        # the old product is replaced outright, not upserted
        assert backfill["datetime"].dt.year().unique().to_list() == [2015]
        assert backfill["precipitation"].to_list() == [1.0, 8.0, 8.0]

    def test_incremental_upserts_refresh_years(
        self, tmp_data_dir, monkeypatch, station_csvs, samples
    ):
        ministry, era5 = samples
        monkeypatch.setattr(weather, "_years_to_refresh", lambda today: [2015])
        old = pl.DataFrame(
            {
                "climate_id": ["7060225"] * 2,
                "datetime": [datetime(2014, 7, 1), datetime(2015, 7, 1)],
                "precipitation": [5.0, 5.0],
                "temperature": [-5.0, -5.0],
            }
        )
        path = tmp_data_dir / "raw" / weather.stations_backfill_file
        path.parent.mkdir(exist_ok=True, parents=True)
        old.write_ipc(path)

        monkeypatch.setattr(
            weather, "_sample_ministry_grid", lambda inv, years: ministry
        )
        monkeypatch.setattr(
            weather, "_sample_era5_cells", lambda inv, years: era5
        )
        weather.update_stations_backfill()

        backfill = pl.read_ipc(path, memory_map=False)
        cutoff = datetime(2015, 1, 1)
        assert backfill.filter(pl.col("datetime") < cutoff).equals(old.head(1))
        assert backfill.filter(pl.col("datetime") >= cutoff)[
            "precipitation"
        ].to_list() == [1.0, 8.0, 8.0]


class TestRebuildCompletedStations:
    def test_missing_backfill_raises(self, tmp_data_dir, station_csvs):
        with pytest.raises(MissingDataError, match="update_stations_backfill"):
            weather.rebuild_completed_stations()

    def test_rebuilds_every_station(
        self, tmp_data_dir, station_csvs, backfill_product
    ):
        weather.rebuild_completed_stations()

        directory = tmp_data_dir / "raw" / "weather" / "stations_completed"
        assert len(list(directory.glob("*.ipc"))) == len(
            weather.stations_files
        )
        completed = pl.read_ipc(directory / "7060225.ipc", memory_map=False)
        # observed days win, backfill fills the rest of the span
        observed = completed.filter(pl.col("datetime") == datetime(2015, 1, 2))
        assert observed["precipitation"][0] == 1.0
        filled = completed.filter(pl.col("datetime") == datetime(2015, 1, 6))
        assert filled["precipitation"][0] == 9.0
        # the day with only temperature observed takes precipitation from
        # the backfill
        partial = completed.filter(pl.col("datetime") == datetime(2015, 1, 4))
        assert partial["precipitation"][0] == 9.0
        assert partial["temperature"][0] == 2.0
        assert no_part_files(tmp_data_dir)


class TestRebuildNearestStations:
    def write_completed(self, tmp_data_dir) -> None:
        days = pl.datetime_range(
            datetime(2015, 1, 1),
            datetime(2015, 1, 6),
            interval="1d",
            eager=True,
        )
        directory = tmp_data_dir / "raw" / "weather" / "stations_completed"
        directory.mkdir(exist_ok=True, parents=True)
        for climate_id in weather.stations_files:
            pl.DataFrame(
                {
                    "datetime": days,
                    "precipitation": np.full(len(days), 1.0),
                    "temperature": np.full(len(days), 0.0),
                    "climate_id": np.full(len(days), climate_id),
                }
            ).write_ipc(directory / f"{climate_id}.ipc")

    def test_missing_completed_station_raises(
        self, tmp_data_dir, station_csvs, stations_df
    ):
        with pytest.raises(
            MissingDataError, match="rebuild_completed_stations"
        ):
            weather.rebuild_nearest_stations(stations_df)

    def test_writes_every_slider_position(
        self, tmp_data_dir, station_csvs, stations_df
    ):
        self.write_completed(tmp_data_dir)
        weather.rebuild_nearest_stations(stations_df)

        for n_stations in range(
            weather.min_n_stations, weather.max_n_stations + 1
        ):
            data = pl.read_ipc(
                tmp_data_dir
                / "raw"
                / f"weather/nearest_stations_{n_stations}.ipc",
                memory_map=False,
            )
            assert sorted(data["id"].unique()) == ["061004", "061020"]
            # constant series: the IDW mean is the constant
            assert data["precipitation"].to_list() == pytest.approx(
                [1.0] * data.height
            )
        assert no_part_files(tmp_data_dir)

    def test_empty_stations_write_empty_products(
        self, tmp_data_dir, station_csvs, stations_df
    ):
        weather.rebuild_nearest_stations(stations_df.clear())
        data = pl.read_ipc(
            tmp_data_dir / "raw" / "weather" / "nearest_stations_1.ipc",
            memory_map=False,
        )
        assert data.is_empty()
        assert data.columns == [
            "id",
            "datetime",
            "precipitation",
            "temperature",
        ]


class TestRebuildGrids:
    def test_writes_the_three_grid_products(
        self, tmp_data_dir, monkeypatch, stations_df, grid_df
    ):
        for target in (
            "_era5_grid",
            "_ministry_grid_grid",
            "_nearest_stations_grid",
        ):
            monkeypatch.setattr(weather, target, lambda polygons: grid_df)
        weather.rebuild_grids(stations_df)

        for name in ("era5", "ministry_grid", "nearest_stations"):
            data = pl.read_ipc(
                tmp_data_dir / "raw" / "weather" / f"grid_{name}.ipc",
                memory_map=False,
            )
            assert data.equals(grid_df)
        assert no_part_files(tmp_data_dir)


class TestYearsToRefresh:
    def test_normal_month_refreshes_current_year(self):
        assert weather._years_to_refresh(date(2026, 8, 15)) == [2026]

    def test_january_also_refreshes_previous_year(self):
        assert weather._years_to_refresh(date(2026, 1, 5)) == [2025, 2026]


class TestStationYears:
    def test_empty_stations_raise(self, stations_df):
        with pytest.raises(ValueError, match="No stations"):
            weather._station_years(stations_df.clear(), 1940)

    def test_clamps_to_start_year(self, stations_df):
        stations = stations_df.with_columns(pl.lit(1910).alias("start"))
        assert weather._station_years(stations, 1940) == [*range(1940, 2018)]

    def test_open_ended_record_runs_to_current_year(self, stations_df):
        stations = stations_df.with_columns(
            pl.lit(None, dtype=pl.Int64).alias("end")
        )
        years = weather._station_years(stations, 1940)
        assert years[0] == 2015
        assert years[-1] == date.today().year


class TestUpsertProduct:
    def test_replaces_rows_from_cutoff(self):
        product = make_product(["a"], [2015, 2016])
        new = pl.DataFrame(
            {
                "id": ["a"],
                "datetime": [datetime(2016, 6, 1)],
                "precipitation": [7.0],
                "temperature": [-7.0],
            }
        )
        upserted = weather._upsert_product(
            product, new, 2016, ("id", "datetime")
        )
        assert upserted.filter(
            pl.col("datetime") < datetime(2016, 1, 1)
        ).equals(product.filter(pl.col("datetime") < datetime(2016, 1, 1)))
        assert upserted.filter(pl.col("datetime") >= datetime(2016, 1, 1))[
            "precipitation"
        ].to_list() == [7.0]


class TestWriteIpc:
    def test_stages_and_replaces(self, tmp_data_dir, weather_df):
        path = tmp_data_dir / "raw" / "weather" / "product.ipc"
        weather._write_ipc(path, weather_df)
        assert pl.read_ipc(path, memory_map=False).equals(weather_df)
        assert not path.with_suffix(".part").exists()


class TestUnlinkLegacyEra5Spans:
    def test_missing_directory_is_fine(self, tmp_data_dir):
        weather._unlink_legacy_era5_spans()

    def test_unlinks_span_files_only(self, tmp_data_dir):
        directory = tmp_data_dir / "raw" / "weather" / "era5"
        directory.mkdir(exist_ok=True, parents=True)
        legacy = directory / "47.75_-71.25_1940_2024.ipc"
        legacy.write_bytes(b"legacy")
        yearly = directory / "47.75_-71.25_2024.ipc"
        yearly.write_bytes(b"yearly")
        weather._unlink_legacy_era5_spans()
        assert not legacy.exists()
        assert yearly.exists()


class TestEnsureEra5Cells:
    def test_cached_cells_skip_credentials(self, tmp_data_dir, monkeypatch):
        path = weather._era5_cell_year_path(47.75, -71.25, 2015)
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(b"cached")
        check = MagicMock(side_effect=AssertionError("must not be called"))
        monkeypatch.setattr(weather, "_check_era5_credentials", check)
        fetched = weather._ensure_era5_cells(
            [(47.75, -71.25)], [2015], refetch=False
        )
        assert fetched == 0
        assert path.exists()

    def test_missing_cells_check_credentials_once(
        self, tmp_data_dir, monkeypatch
    ):
        check = MagicMock()
        fetch = MagicMock()
        monkeypatch.setattr(weather, "_check_era5_credentials", check)
        monkeypatch.setattr(weather, "_fetch_era5_cell_years", fetch)
        fetched = weather._ensure_era5_cells(
            [(47.75, -71.25), (48.0, -71.25)], [2015], refetch=False
        )
        assert fetched == 2
        check.assert_called_once()
        assert fetch.call_count == 2

    def test_refetch_drops_cached_years(self, tmp_data_dir, monkeypatch):
        path = weather._era5_cell_year_path(47.75, -71.25, 2015)
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_bytes(b"stale")
        monkeypatch.setattr(weather, "_check_era5_credentials", MagicMock())
        fetch = MagicMock()
        monkeypatch.setattr(weather, "_fetch_era5_cell_years", fetch)
        fetched = weather._ensure_era5_cells(
            [(47.75, -71.25)], [2015], refetch=True
        )
        assert fetched == 1
        assert not path.exists()
        fetch.assert_called_once_with(47.75, -71.25, [2015])


class TestFetchEra5CellYears:
    def test_splits_years_and_skips_partial_edges(
        self, tmp_data_dir, monkeypatch
    ):
        # data covers 2015 only: 2016 was clipped by CDS, and the shift
        # spills the first UTC hours into local 2014
        monkeypatch.setattr(
            weather,
            "_download_era5_cell_range",
            lambda latitude, longitude, start, end: make_hourly(
                datetime(2015, 1, 1), datetime(2015, 12, 31, 23)
            ),
        )
        weather._fetch_era5_cell_years(47.75, -71.25, [2015, 2016])

        assert not weather._era5_cell_year_path(47.75, -71.25, 2014).exists()
        assert not weather._era5_cell_year_path(47.75, -71.25, 2016).exists()
        data = pl.read_ipc(
            weather._era5_cell_year_path(47.75, -71.25, 2015),
            memory_map=False,
        )
        assert data["datetime"].min() == datetime(2015, 1, 1)
        assert data["datetime"].max() == datetime(2015, 12, 31)
        assert data["latitude"].unique().to_list() == [47.75]
        assert no_part_files(tmp_data_dir)


class TestDownloadEra5CellRange:
    @staticmethod
    def make_client(
        files: dict[str, bytes], requests: list[dict]
    ) -> MagicMock:
        def retrieve(dataset, request, archive):
            requests.append(request)
            with zipfile.ZipFile(archive, "w") as z:
                for name, content in files.items():
                    z.writestr(name, content)

        client = MagicMock()
        client.retrieve.side_effect = retrieve
        return client

    def test_requests_range_and_concats_csvs(self, monkeypatch):
        requests: list[dict] = []
        client = self.make_client(
            {
                "a.csv": b"valid_time,tp,t2m\n2015-01-01 00:00:00,0.001,273\n",
                "b.csv": b"valid_time,tp,t2m\n2015-01-01 01:00:00,0.002,274\n",
            },
            requests,
        )
        monkeypatch.setattr(
            weather.cdsapi, "Client", MagicMock(return_value=client)
        )
        data = weather._download_era5_cell_range(47.75, -71.25, 2015, 2016)
        assert data.height == 2
        # the extra two days close local Dec 31 of the last year
        assert requests[0]["date"] == ["2015-01-01/2017-01-02"]

    def test_zip_without_csv_raises(self, monkeypatch):
        client = self.make_client({"readme.txt": b"no data"}, [])
        monkeypatch.setattr(
            weather.cdsapi, "Client", MagicMock(return_value=client)
        )
        with pytest.raises(ValueError, match="no csv"):
            weather._download_era5_cell_range(47.75, -71.25, 2015, 2016)


class TestReduceEra5Cell:
    def test_accumulation_shift_and_units(self):
        # 05:00 UTC is local (UTC-5) midnight; the end-of-hour stamp shifts
        # it back to the previous local day
        data = pl.DataFrame(
            {
                "valid_time": [
                    "2015-01-02 04:00:00",
                    "2015-01-02 05:00:00",
                    "2015-01-02 06:00:00",
                ],
                "tp": [0.001, 0.002, 0.004],
                "t2m": [273.15, 274.15, 275.15],
            }
        )
        reduced = weather._reduce_era5_cell(data, 47.75, -71.25)
        jan_1 = reduced.filter(pl.col("datetime") == datetime(2015, 1, 1))
        jan_2 = reduced.filter(pl.col("datetime") == datetime(2015, 1, 2))
        # 04:00Z and 05:00Z belong to Jan 1 local, 06:00Z to Jan 2
        assert jan_1["precipitation"][0] == pytest.approx(3.0)
        assert jan_2["precipitation"][0] == pytest.approx(4.0)
        assert jan_1["temperature"][0] == pytest.approx(0.5)
        assert jan_1["latitude"][0] == 47.75


class TestReadEra5Years:
    def test_concats_cached_years(self, tmp_data_dir):
        cell = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        )
        path = weather._era5_cell_year_path(47.75, -71.25, 2015)
        path.parent.mkdir(exist_ok=True, parents=True)
        cell.write_ipc(path)
        data = weather._read_era5_years([(47.75, -71.25)], [2015])
        assert data.equals(cell)

    def test_missing_trailing_year_is_skipped(self, tmp_data_dir, monkeypatch):
        cell = pl.DataFrame(
            {
                "datetime": [datetime(2025, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        )
        path = weather._era5_cell_year_path(47.75, -71.25, 2025)
        path.parent.mkdir(exist_ok=True, parents=True)
        cell.write_ipc(path)
        warn = MagicMock()
        monkeypatch.setattr(weather, "warn_print", warn)
        # early January: CDS has not reached 2026 yet
        data = weather._read_era5_years([(47.75, -71.25)], [2025, 2026])
        assert data.equals(cell)
        warn.assert_called_once()

    def test_partial_year_coverage_raises(self, tmp_data_dir):
        cell = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        )
        path = weather._era5_cell_year_path(47.75, -71.25, 2015)
        path.parent.mkdir(exist_ok=True, parents=True)
        cell.write_ipc(path)
        with pytest.raises(RuntimeError, match="Missing ERA5 cell files"):
            weather._read_era5_years([(47.75, -71.25), (48.0, -71.25)], [2015])

    def test_no_data_at_all_raises(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(weather, "warn_print", MagicMock())
        with pytest.raises(RuntimeError, match="No ERA5 data"):
            weather._read_era5_years([(47.75, -71.25)], [2015])


class TestComputeEra5Means:
    def test_weighted_mean_over_cells(self):
        grid = pl.DataFrame(
            {
                "id": ["061004", "061004"],
                "latitude": [47.75, 48.0],
                "longitude": [-71.25, -71.25],
                "weight": [1.0, 3.0],
            }
        )
        series = pl.DataFrame(
            {
                "latitude": [47.75, 48.0],
                "longitude": [-71.25, -71.25],
                "datetime": [datetime(2015, 1, 1)] * 2,
                "precipitation": [1.0, 5.0],
                "temperature": [0.0, 4.0],
            }
        )
        means = weather._compute_era5_means(grid, series)
        assert means["precipitation"].to_list() == [
            pytest.approx((1.0 * 1 + 5.0 * 3) / 4)
        ]
        assert means["temperature"].to_list() == [pytest.approx(3.0)]


class TestCheckEra5Credentials:
    def test_no_credentials_raises_with_instructions(self, monkeypatch):
        monkeypatch.setattr(
            weather.cdsapi,
            "Client",
            MagicMock(side_effect=Exception("no token")),
        )
        with pytest.raises(RuntimeError, match="CDSAPI_KEY"):
            weather._check_era5_credentials()

    def test_valid_credentials_pass(self, monkeypatch):
        monkeypatch.setattr(weather.cdsapi, "Client", MagicMock())
        weather._check_era5_credentials()


class TestEra5Lattice:
    @pytest.mark.parametrize(
        ["value", "expected"],
        [(48.13, 48.25), (47.7, 47.75), (-71.3, -71.25), (-71.38, -71.5)],
    )
    def test_snaps_to_quarter_degree(self, value, expected):
        assert weather._era5_lattice(value) == expected


class TestEra5Grid:
    def test_cells_cover_watersheds(self, polygons):
        grid = weather._era5_grid(polygons.to_crs("EPSG:4326"))
        assert set(grid["id"].unique()) == {"061004", "061020"}
        assert (grid["weight"] > 0).all()
        # centres sit on the 0.25 deg lattice
        for value in grid["latitude"]:
            assert round(value / weather.era5_resolution, 6) % 1 == 0

    def test_degenerate_watershed_raises(self):
        # a point-like polygon stays zero-area through any reprojection (a
        # collinear one would curve into positive area in Lambert)
        point = [(-71.3, 47.7)] * 3
        flat = gpd.GeoDataFrame(
            {"id": ["x"], "geometry": [shapely.Polygon(point)]},
            crs="EPSG:4326",
        )
        with pytest.raises(ValueError, match="No ERA5 cell"):
            weather._era5_grid(flat)

    def test_empty_polygons_return_empty_grid(self, empty_polygons):
        grid = weather._era5_grid(empty_polygons.to_crs("EPSG:4326"))
        assert grid.is_empty()


class TestEra5CellsCovering:
    def test_covers_bounds(self):
        cells = weather._era5_cells_covering((-71.3, 47.7, -71.2, 47.8))
        union = shapely.unary_union(cells)
        assert union.contains(shapely.box(-71.3, 47.7, -71.2, 47.8))
        for cell in cells:
            centre = cell.centroid
            assert round(centre.x / weather.era5_resolution, 6) % 1 == 0
            assert round(centre.y / weather.era5_resolution, 6) % 1 == 0


class TestBuildMinistryGrid:
    def test_no_years_returns_typed_empty(self, monkeypatch, polygons):
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year: None,
        )
        data = weather._build_ministry_grid(polygons, [2015])
        assert data.is_empty()
        assert data.columns == [
            "id",
            "datetime",
            "precipitation",
            "temperature",
        ]


class TestFillMultidayGapsFromEra5:
    def test_fills_runs_and_leaves_isolated_gaps(self):
        days = pl.datetime_range(
            datetime(2015, 1, 1),
            datetime(2015, 1, 5),
            interval="1d",
            eager=True,
        )
        data = pl.DataFrame(
            {
                "id": ["061004"] * 5,
                "datetime": days,
                "precipitation": [1.0, None, None, 4.0, 5.0],
                "temperature": [1.0, None, 3.0, 4.0, 5.0],
            }
        )
        era5 = pl.DataFrame(
            {
                "id": ["061004"] * 5,
                "datetime": days,
                "precipitation": [8.0] * 5,
                "temperature": [-8.0] * 5,
            }
        )
        filled = weather._fill_multiday_gaps_from_era5(data, era5)
        # the two-day run is filled from era5, the isolated gap is left
        assert filled["precipitation"].to_list() == [1.0, 8.0, 8.0, 4.0, 5.0]
        assert filled["temperature"].to_list() == [1.0, None, 3.0, 4.0, 5.0]


class TestMultidayGapMask:
    def test_marks_runs_of_two_or_more(self):
        days = pl.datetime_range(
            datetime(2015, 1, 1),
            datetime(2015, 1, 6),
            interval="1d",
            eager=True,
        )
        data = pl.DataFrame(
            {
                "id": ["a"] * 6,
                "datetime": days,
                "value": [1.0, None, 1.0, None, float("nan"), 1.0],
            }
        )
        mask = data.select(weather._multiday_gap_mask("value").alias("mask"))[
            "mask"
        ]
        # the isolated gap stays False; the null+NaN run is True
        assert mask.to_list() == [False, False, False, True, True, False]


class TestReadYearMinistryGridWeatherData:
    def test_missing_file_returns_none(self, monkeypatch):
        monkeypatch.setattr(weather, "_ministry_grid_file", lambda name: None)
        assert weather._read_year_ministry_grid_weather_data(2015) is None

    def test_merges_and_renames(self, tmp_path, monkeypatch, polygons):
        source = make_ministry_dataset(polygons, 2015)
        prec_path = tmp_path / "PREC_2015.nc"
        tmoy_path = tmp_path / "TMOY_2015.nc"
        source[["PREC"]].to_netcdf(prec_path)
        source[["TMOY"]].to_netcdf(tmoy_path)
        monkeypatch.setattr(
            weather,
            "_ministry_grid_file",
            lambda name: prec_path if name.startswith("PREC") else tmoy_path,
        )
        data = weather._read_year_ministry_grid_weather_data(2015)
        assert data is not None
        assert set(data.data_vars) == {"precipitation", "temperature"}
        assert data.rio.crs.to_string() == crs


class TestDownloadMinistryGridFiles:
    def test_nothing_missing_returns_early(self, tmp_data_dir, monkeypatch):
        directory = tmp_data_dir / "raw" / "weather" / "ministry_grid"
        directory.mkdir(exist_ok=True, parents=True)
        (directory / "PREC_2015.nc").touch()
        download = MagicMock(side_effect=AssertionError("must not download"))
        monkeypatch.setattr(weather, "_ministry_grid_file", download)
        weather._download_ministry_grid_files(["PREC_2015.nc"])

    def test_downloads_missing_concurrently(self, tmp_data_dir, monkeypatch):
        seen: list[str] = []
        monkeypatch.setattr(
            weather,
            "_ministry_grid_file",
            lambda name: seen.append(name),
        )
        weather._download_ministry_grid_files(["PREC_2015.nc", "TMOY_2015.nc"])
        assert sorted(seen) == ["PREC_2015.nc", "TMOY_2015.nc"]


class TestMinistryGridFile:
    def test_cache_hit(self, tmp_data_dir):
        path = tmp_data_dir / "raw" / "weather" / "ministry_grid" / "a.nc"
        path.parent.mkdir(exist_ok=True, parents=True)
        path.touch()
        assert weather._ministry_grid_file("a.nc") == path

    def test_downloads_and_validates(
        self, tmp_data_dir, tmp_path, monkeypatch, polygons
    ):
        source_path = tmp_path / "source.nc"
        make_ministry_dataset(polygons, 2015).to_netcdf(source_path)
        body = source_path.read_bytes()
        monkeypatch.setattr(
            weather.httpx,
            "stream",
            lambda method, url, **kwargs: make_response(body),
        )
        path = weather._ministry_grid_file("PREC_2015.nc")
        assert path is not None
        assert path.exists()
        xr.open_dataset(path).close()

    def test_http_error_returns_none(self, tmp_data_dir, monkeypatch):
        resp = make_response(b"")
        resp.raise_for_status.side_effect = RuntimeError("503")
        monkeypatch.setattr(
            weather.httpx, "stream", lambda method, url, **kwargs: resp
        )
        assert weather._ministry_grid_file("PREC_2015.nc") is None

    def test_corrupt_body_returns_none(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(
            weather.httpx,
            "stream",
            lambda method, url, **kwargs: make_response(b"<html>error</html>"),
        )
        assert weather._ministry_grid_file("PREC_2015.nc") is None
        directory = tmp_data_dir / "raw" / "weather" / "ministry_grid"
        assert not (directory / "PREC_2015.nc").exists()
        # a failed attempt must not strand a stale .part file either
        assert not list(directory.glob("*.part"))


class TestReadStationInventory:
    def test_span_covers_observed_days_only(self, station_csvs):
        inventory = weather._read_station_inventory()
        assert inventory.height == len(weather.stations_files)
        row = inventory.filter(pl.col("climate_id") == "7060225")
        assert row["start"][0] == date(2015, 1, 2)
        assert row["end"][0] == date(2015, 1, 4)


class TestReadStationCsv:
    def test_missing_csv_raises(self, tmp_data_dir):
        with pytest.raises(MissingDataError, match="no public source"):
            weather._read_station_csv(weather.stations_files["7060225"][0])


class TestSampleMinistryGrid:
    @pytest.fixture
    def inventory(self) -> pl.DataFrame:
        return pl.DataFrame(
            {
                "climate_id": ["7060225"],
                "name": ["Pikauba"],
                "longitude": [-71.3],
                "latitude": [47.7],
                "start": [date(2015, 1, 1)],
                "end": [date(2015, 1, 3)],
            }
        )

    def test_samples_station_cells(self, monkeypatch, polygons, inventory):
        processed = make_processed_dataset(polygons, 2015)
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year: processed if year == 2015 else None,
        )
        data = weather._sample_ministry_grid(inventory, [2014, 2015])
        assert data["climate_id"].unique().to_list() == ["7060225"]
        # the 05:00 stamp collapses to the calendar date
        assert data["datetime"].to_list() == [
            datetime(2015, 1, 1),
            datetime(2015, 1, 2),
            datetime(2015, 1, 3),
        ]
        assert data["precipitation"].to_list() == [2.0, 2.0, 2.0]

    def test_no_year_available_returns_empty(self, monkeypatch, inventory):
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year: None,
        )
        data = weather._sample_ministry_grid(inventory, [2015])
        assert data.is_empty()
        assert data.schema == weather._empty_backfill_frame().schema


class TestSampleEra5Cells:
    def test_shared_cell_is_read_once_per_station(self, tmp_data_dir):
        # both stations snap to the same 0.25 deg cell
        inventory = pl.DataFrame(
            {
                "climate_id": ["7060225", "7061439"],
                "name": ["Pikauba", "Chicoutimi"],
                "longitude": [-71.3, -71.26],
                "latitude": [47.7, 47.76],
                "start": [date(2015, 1, 1)] * 2,
                "end": [date(2015, 1, 3)] * 2,
            }
        )
        cell = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [-1.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        )
        path = weather._era5_cell_year_path(47.75, -71.25, 2015)
        path.parent.mkdir(exist_ok=True, parents=True)
        cell.write_ipc(path)
        data = weather._sample_era5_cells(inventory, [2015])
        assert data["climate_id"].to_list() == ["7060225", "7061439"]
        assert data["precipitation"].to_list() == [1.0, 1.0]


class TestCoalesceBackfill:
    def test_ministry_wins_over_era5(self):
        days = pl.datetime_range(
            datetime(2015, 1, 1),
            datetime(2015, 1, 3),
            interval="1d",
            eager=True,
        )
        ministry = pl.DataFrame(
            {
                "climate_id": ["7060225"] * 2,
                "datetime": days[:2],
                "precipitation": [1.0, None],
                "temperature": [-1.0, -2.0],
            }
        )
        era5 = pl.DataFrame(
            {
                "climate_id": ["7060225"] * 3,
                "datetime": days,
                "precipitation": [8.0, 8.0, 8.0],
                "temperature": [-8.0, -8.0, -8.0],
            }
        )
        backfill = weather._coalesce_backfill(ministry, era5)
        assert backfill["precipitation"].to_list() == [1.0, 8.0, 8.0]
        assert backfill["temperature"].to_list() == [-1.0, -2.0, -8.0]


class TestReadBackfillProduct:
    def test_missing_raises(self, tmp_data_dir):
        with pytest.raises(MissingDataError, match="update_stations_backfill"):
            weather._read_backfill_product()


class TestCompleteStationSeries:
    def test_observed_days_outside_backfill_are_kept(self):
        observed = pl.DataFrame(
            {
                "datetime": [datetime(2010, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
                "climate_id": ["x"],
            }
        )
        backfill = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [9.0],
                "temperature": [-9.0],
            }
        )
        completed = weather._complete_station_series(observed, backfill, "x")
        assert completed["datetime"].to_list() == [
            datetime(2010, 1, 1),
            datetime(2015, 1, 1),
        ]
        assert completed["precipitation"].to_list() == [1.0, 9.0]


class TestReadCompletedStationProduct:
    def test_missing_raises(self, tmp_data_dir):
        with pytest.raises(
            MissingDataError, match="rebuild_completed_stations"
        ):
            weather._read_completed_station_product("7060225")


class TestSelectNearestStations:
    def test_orders_by_distance_and_weights(self, polygons):
        inventory = pl.DataFrame(
            {
                "climate_id": ["far", "near"],
                "name": ["Far", "Near"],
                "longitude": [-70.0, -71.3],
                "latitude": [49.0, 47.7],
                "start": [date(2015, 1, 1)] * 2,
                "end": [date(2017, 12, 31)] * 2,
            }
        )
        selection = weather._select_nearest_stations(
            polygons, inventory, 2
        ).filter(pl.col("id") == "061004")
        assert selection["climate_id"].to_list() == ["near", "far"]
        assert selection["weight"][0] > selection["weight"][1]

    def test_station_on_centroid_gets_floored_distance(self, polygons):
        # the centroid is taken in the projected crs, so the station must
        # be placed at that projected point sent back to lat/lon
        centroid = (
            gpd.GeoSeries([polygons.geometry.iloc[0].centroid], crs=crs)
            .to_crs("EPSG:4326")
            .iloc[0]
        )
        inventory = pl.DataFrame(
            {
                "climate_id": ["centre"],
                "name": ["Centre"],
                "longitude": [centroid.x],
                "latitude": [centroid.y],
                "start": [date(2015, 1, 1)],
                "end": [date(2017, 12, 31)],
            }
        )
        selection = weather._select_nearest_stations(polygons, inventory, 1)
        assert selection.filter(pl.col("id") == "061004")["distance"][
            0
        ] == pytest.approx(1.0)


class TestCombineIdw:
    def test_renormalizes_daily_and_densifies(self):
        selection = pl.DataFrame(
            {
                "id": ["061004", "061004"],
                "climate_id": ["a", "b"],
                "weight": [1.0, 3.0],
            }
        )
        series = pl.DataFrame(
            {
                "climate_id": ["a", "b", "a", "b", "a", "b"],
                "datetime": [
                    datetime(2015, 1, 1),
                    datetime(2015, 1, 1),
                    datetime(2015, 1, 2),
                    datetime(2015, 1, 2),
                    datetime(2015, 1, 4),
                    datetime(2015, 1, 4),
                ],
                "precipitation": [1.0, 2.0, None, 4.0, None, None],
                "temperature": [0.0, 4.0, 1.0, 5.0, 2.0, 6.0],
            }
        )
        combined = weather._combine_idw(selection, series)
        # both report: weighted mean; one reports: its value; none: null
        assert combined["precipitation"].to_list() == [
            pytest.approx((1.0 * 1 + 2.0 * 3) / 4),
            4.0,
            None,
            None,
        ]
        # the missing Jan 3 is densified in as null
        assert combined["datetime"].dt.day().to_list() == [1, 2, 3, 4]


class TestTrimNullEdges:
    def test_trims_per_station(self):
        days = pl.datetime_range(
            datetime(2015, 1, 1),
            datetime(2015, 1, 4),
            interval="1d",
            eager=True,
        )
        data = pl.DataFrame(
            {
                "id": ["a"] * 4 + ["b"] * 4,
                "datetime": pl.concat([days, days]),
                "precipitation": [None, 1.0, None, 2.0, 1.0, 2.0, 3.0, None],
                "temperature": [0.0, 1.0, None, 2.0, 1.0, 2.0, 3.0, None],
            }
        )
        trimmed = weather._trim_null_edges(data)
        assert trimmed.filter(pl.col("id") == "a")[
            "datetime"
        ].dt.day().to_list() == [2, 3, 4]
        assert trimmed.filter(pl.col("id") == "b")[
            "datetime"
        ].dt.day().to_list() == [1, 2, 3]


class TestMinistryGridGrid:
    def write_raster(self, tmp_data_dir, polygons, n: int = 6) -> Path:
        directory = tmp_data_dir / "raw" / "weather" / "ministry_grid"
        directory.mkdir(exist_ok=True, parents=True)
        path = directory / "PREC_2015.nc"
        source = make_ministry_dataset(polygons, 2015)
        if n < 6:
            source = source.isel(x=slice(0, n), y=slice(0, n))
        source.to_netcdf(path)
        return path

    def test_no_raster_returns_empty_grid(self, monkeypatch, polygons):
        monkeypatch.setattr(weather, "_any_ministry_grid_file", lambda: None)
        grid = weather._ministry_grid_grid(polygons.to_crs("EPSG:4326"))
        assert grid.is_empty()

    def test_single_cell_lattice_raises(
        self, tmp_data_dir, monkeypatch, polygons
    ):
        self.write_raster(tmp_data_dir, polygons, n=1)
        with pytest.raises(ValueError, match="too few cells"):
            weather._ministry_grid_grid(polygons.to_crs("EPSG:4326"))

    def test_watershed_outside_lattice_raises(self, tmp_data_dir, polygons):
        self.write_raster(tmp_data_dir, polygons)
        outside = gpd.GeoDataFrame(
            {
                "id": ["x"],
                "geometry": [shapely.box(10.0, 10.0, 10.1, 10.1)],
            },
            crs="EPSG:4326",
        )
        with pytest.raises(ValueError, match="No ministry grid cell"):
            weather._ministry_grid_grid(outside)

    def test_cells_cover_watersheds(self, tmp_data_dir, polygons):
        self.write_raster(tmp_data_dir, polygons)
        grid = weather._ministry_grid_grid(polygons.to_crs("EPSG:4326"))
        assert set(grid["id"].unique()) == {"061004", "061020"}
        assert (grid["weight"] > 0).all()

    def test_zero_area_watershed_yields_empty_grid(
        self, tmp_data_dir, polygons
    ):
        # inside the lattice, so cells are found, but every intersection
        # has zero area and is skipped
        self.write_raster(tmp_data_dir, polygons)
        point = [(-71.3, 47.7)] * 3
        flat = gpd.GeoDataFrame(
            {"id": ["x"], "geometry": [shapely.Polygon(point)]},
            crs="EPSG:4326",
        )
        assert weather._ministry_grid_grid(flat).is_empty()


class TestAnyMinistryGridFile:
    def test_prefers_cached_file(self, tmp_data_dir, monkeypatch):
        directory = tmp_data_dir / "raw" / "weather" / "ministry_grid"
        directory.mkdir(exist_ok=True, parents=True)
        cached = directory / "PREC_1990.nc"
        cached.touch()
        download = MagicMock(side_effect=AssertionError("must not download"))
        monkeypatch.setattr(weather, "_ministry_grid_file", download)
        assert weather._any_ministry_grid_file() == cached

    def test_falls_back_to_download(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(
            weather, "_ministry_grid_file", lambda name: Path("/dl") / name
        )
        assert weather._any_ministry_grid_file() == Path("/dl/PREC_1940.nc")


class TestNearestStationsGrid:
    def test_empty_polygons_return_empty_grid(
        self, station_csvs, empty_polygons
    ):
        grid = weather._nearest_stations_grid(
            empty_polygons.to_crs("EPSG:4326")
        )
        assert grid.is_empty()

    def test_full_pool_with_metadata(self, station_csvs, polygons):
        grid = weather._nearest_stations_grid(polygons.to_crs("EPSG:4326"))
        assert grid.filter(pl.col("id") == "061004").height == (
            weather.max_n_stations
        )
        row = grid.row(0, named=True)
        assert row["climate_id"] in weather.stations_files
        assert row["name"]
        assert row["start"] is not None
        point = shapely.from_geojson(row["geometry"])
        assert point.geom_type == "Point"
