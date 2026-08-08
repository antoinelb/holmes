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

import holmes.data.weather as weather

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
        # the record opens with an unobserved day, so the inventory span must
        # start on the first day carrying any value
        path.write_text(
            "datetime,lat,lon,precipitation,tmax,tmin,temperature\n"
            f"2015-01-01,{lat},{lon},,,,\n"
            f"2015-01-02,{lat},{lon},1.0,2.0,-2.0,0.0\n"
            f"2015-01-03,{lat},{lon},2.0,3.0,-1.0,1.0\n"
            f"2015-01-04,{lat},{lon},,4.0,0.0,2.0\n"
        )


@pytest.fixture
def backfill_file(tmp_data_dir: Path) -> pl.DataFrame:
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
    resp = MagicMock()
    resp.content = content
    return resp


class TestReadWeatherData:
    def test_invalid_n_stations_raises(self, stations_df):
        with pytest.raises(ValueError, match="n_stations"):
            weather.read_weather_data(
                stations_df, method="nearest_stations", n_stations=6
            )

    def test_cache_hit(self, tmp_data_dir, stations_df, weather_df):
        path = tmp_data_dir / "raw" / "weather" / "nearest_stations_3.ipc"
        path.parent.mkdir(parents=True)
        weather_df.write_ipc(path)
        data = weather.read_weather_data(
            stations_df, method="nearest_stations"
        )
        assert data.equals(weather_df)

    def test_era5_release_asset_first(
        self, tmp_data_dir, monkeypatch, stations_df, weather_df
    ):
        def fake_asset(asset, path):
            assert asset == "era5.ipc"
            path.parent.mkdir(exist_ok=True, parents=True)
            weather_df.write_ipc(path)
            return True

        monkeypatch.setattr(weather, "download_release_asset", fake_asset)
        data = weather.read_weather_data(stations_df, method="era5")
        assert data.equals(weather_df)

    def test_era5_published_fallback(
        self, tmp_data_dir, monkeypatch, stations_df, weather_df
    ):
        def fake_published(name):
            assert name == "weather/era5.ipc"
            path = tmp_data_dir / "raw" / name
            path.parent.mkdir(exist_ok=True, parents=True)
            weather_df.write_ipc(path)
            return True

        monkeypatch.setattr(
            weather, "download_release_asset", lambda asset, path: False
        )
        monkeypatch.setattr(weather, "download_published_file", fake_published)
        data = weather.read_weather_data(stations_df, method="era5")
        assert data.equals(weather_df)

    def test_rebuild_skips_downloads_and_clamps_years(
        self, tmp_data_dir, monkeypatch, stations_df, weather_df
    ):
        release = MagicMock()
        published = MagicMock()
        monkeypatch.setattr(weather, "download_release_asset", release)
        monkeypatch.setattr(weather, "download_published_file", published)
        read = MagicMock(return_value=weather_df)
        monkeypatch.setattr(weather, "_read_era5_weather_data", read)

        # a pre-1940 record start must clamp to the era5 origin
        stations = stations_df.with_columns(
            pl.when(pl.col("id") == "061004")
            .then(1910)
            .otherwise(pl.col("start"))
            .alias("start")
        )
        data = weather.read_weather_data(stations, method="era5", rebuild=True)
        release.assert_not_called()
        published.assert_not_called()
        assert read.call_args.args[1] == weather.era5_start_year
        assert data.equals(weather_df)
        cached = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        assert cached.exists()

    def test_nearest_stations_trims_edges(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        raw = pl.DataFrame(
            {
                "id": ["061004"] * 4,
                "datetime": pl.datetime_range(
                    datetime(2015, 1, 1),
                    datetime(2015, 1, 4),
                    interval="1d",
                    eager=True,
                ),
                "precipitation": [None, 1.0, 2.0, None],
                "temperature": [None, 0.0, 1.0, 2.0],
            }
        )
        monkeypatch.setattr(
            weather,
            "_read_nearest_stations_weather_data",
            lambda polygons, n: raw,
        )
        data = weather.read_weather_data(
            stations_df, method="nearest_stations", rebuild=True
        )
        assert data["datetime"].dt.day().to_list() == [2, 3]

    def test_ministry_grid_backfills_from_era5(
        self, tmp_data_dir, monkeypatch, stations_df, weather_df
    ):
        days = pl.datetime_range(
            datetime(2015, 1, 1),
            datetime(2015, 1, 5),
            interval="1d",
            eager=True,
        )
        raw = pl.DataFrame(
            {
                "id": ["061004"] * 5,
                "datetime": days,
                "precipitation": [1.0, None, None, 4.0, 5.0],
                "temperature": [1.0, None, 3.0, 4.0, 5.0],
            }
        )
        monkeypatch.setattr(
            weather,
            "_read_ministry_grid_weather_data",
            lambda polygons, years, crs: raw,
        )
        # the recursion for the reference must hit the era5 cache
        era5_path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        era5_path.parent.mkdir(exist_ok=True, parents=True)
        weather_df.write_ipc(era5_path)

        data = weather.read_weather_data(
            stations_df, method="ministry_grid", rebuild=True
        ).sort("datetime")
        era5 = weather_df.filter(
            (pl.col("id") == "061004")
            & (pl.col("datetime") == datetime(2015, 1, 2))
        )
        # the two-day run is filled from era5, the isolated gap is left
        assert data["precipitation"][1] == era5["precipitation"][0]
        assert data["precipitation"][2] is not None
        assert data["temperature"][1] is None


class TestDownloadReleaseAsset:
    def test_success(self, tmp_data_dir, monkeypatch, weather_df, ipc_bytes):
        monkeypatch.setattr(
            weather.httpx,
            "get",
            lambda url, **kwargs: make_response(ipc_bytes(weather_df)),
        )
        path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        assert weather.download_release_asset("era5.ipc", path)
        assert pl.read_ipc(path).equals(weather_df)

    def test_corrupt_body_is_not_cached(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(
            weather.httpx,
            "get",
            lambda url, **kwargs: make_response(b"<html>error</html>"),
        )
        path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        assert not weather.download_release_asset("era5.ipc", path)
        assert not path.exists()

    def test_http_error_returns_false(self, tmp_data_dir, monkeypatch):
        resp = make_response(b"")
        resp.raise_for_status.side_effect = RuntimeError("404")
        monkeypatch.setattr(weather.httpx, "get", lambda url, **kwargs: resp)
        path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        assert not weather.download_release_asset("era5.ipc", path)


class TestDownloadPublishedFile:
    def test_unknown_name_raises(self):
        with pytest.raises(ValueError, match="Unknown published dataset"):
            weather.download_published_file("weather/unknown.ipc")

    def test_ipc_success(
        self, tmp_data_dir, monkeypatch, weather_df, ipc_bytes
    ):
        monkeypatch.setattr(
            weather.httpx,
            "get",
            lambda url, **kwargs: make_response(ipc_bytes(weather_df)),
        )
        assert weather.download_published_file(weather.stations_backfill_file)
        path = tmp_data_dir / "raw" / weather.stations_backfill_file
        assert pl.read_ipc(path).equals(weather_df)

    def test_csv_success(self, tmp_data_dir, monkeypatch):
        name = weather.stations_files["7060225"][0]
        monkeypatch.setattr(
            weather.httpx,
            "get",
            lambda url, **kwargs: make_response(b"a,b\n1,2\n"),
        )
        assert weather.download_published_file(name)
        assert (tmp_data_dir / "raw" / name).exists()

    def test_corrupt_body_returns_false(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(
            weather.httpx,
            "get",
            lambda url, **kwargs: make_response(b"<html>error</html>"),
        )
        assert not weather.download_published_file(
            weather.stations_backfill_file
        )
        assert not (
            tmp_data_dir / "raw" / weather.stations_backfill_file
        ).exists()


class TestRebuildStationsBackfill:
    def test_ministry_wins_over_era5(self, tmp_data_dir, monkeypatch):
        inventory = pl.DataFrame(
            {
                "climate_id": ["7060225"],
                "name": ["Pikauba"],
                "longitude": [-71.3],
                "latitude": [47.7],
                "start": [date(2015, 1, 1)],
                "end": [date(2015, 1, 3)],
            }
        )
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
        monkeypatch.setattr(
            weather, "_read_station_inventory", lambda: inventory
        )
        monkeypatch.setattr(
            weather, "_sample_ministry_grid", lambda inv, years, crs: ministry
        )
        monkeypatch.setattr(
            weather, "_sample_era5_cells", lambda inv, start, end: era5
        )
        backfill = weather.rebuild_stations_backfill()
        assert backfill["precipitation"].to_list() == [1.0, 8.0, 8.0]
        assert backfill["temperature"].to_list() == [-1.0, -2.0, -8.0]
        assert (tmp_data_dir / "raw" / weather.stations_backfill_file).exists()


class TestReadWeatherGrid:
    @pytest.mark.parametrize(
        ["method", "target"],
        [
            ("era5", "_era5_grid"),
            ("ministry_grid", "_ministry_grid_grid"),
            ("nearest_stations", "_nearest_stations_grid"),
        ],
    )
    def test_dispatches_on_method(
        self, monkeypatch, stations_df, grid_df, method, target
    ):
        monkeypatch.setattr(weather, target, lambda polygons, crs: grid_df)
        assert weather.read_weather_grid(stations_df, method=method).equals(
            grid_df
        )


class TestValidateNStations:
    @pytest.mark.parametrize("n_stations", [0, 6])
    def test_out_of_bounds_raises(self, n_stations):
        with pytest.raises(ValueError, match="n_stations"):
            weather._validate_n_stations(n_stations)

    @pytest.mark.parametrize("n_stations", [1, 3, 5])
    def test_in_bounds_passes(self, n_stations):
        weather._validate_n_stations(n_stations)


class TestReadNearestStationsWeatherData:
    def test_empty_selection_returns_empty_frame(
        self, station_csvs, empty_polygons
    ):
        data = weather._read_nearest_stations_weather_data(empty_polygons, 3)
        assert data.is_empty()
        assert data.columns == [
            "id",
            "datetime",
            "precipitation",
            "temperature",
        ]

    def test_combines_completed_series(
        self, station_csvs, backfill_file, polygons
    ):
        data = weather._read_nearest_stations_weather_data(polygons, 2)
        assert sorted(data["id"].unique()) == ["061004", "061020"]
        # completed series are dense over the backfill span
        assert (
            data.filter(pl.col("id") == "061004")["datetime"].dt.day().max()
            == 6
        )
        assert data["precipitation"].null_count() == 0


class TestReadStationInventory:
    def test_span_covers_observed_days_only(self, station_csvs):
        inventory = weather._read_station_inventory()
        assert inventory.height == len(weather.stations_files)
        row = inventory.filter(pl.col("climate_id") == "7060225")
        assert row["start"][0] == date(2015, 1, 2)
        assert row["end"][0] == date(2015, 1, 4)


class TestReadStationCsv:
    def test_missing_and_undownloadable_raises(self, monkeypatch):
        monkeypatch.setattr(
            weather, "download_published_file", lambda name: False
        )
        with pytest.raises(RuntimeError, match="could not be downloaded"):
            weather._read_station_csv(weather.stations_files["7060225"][0])

    def test_downloads_when_missing(self, tmp_data_dir, monkeypatch):
        name = weather.stations_files["7060225"][0]

        def fake_download(requested):
            path = tmp_data_dir / "raw" / requested
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text(
                "datetime,lat,lon,precipitation,tmax,tmin,temperature\n"
                "2015-01-01,47.7,-71.3,1.0,2.0,-2.0,0.0\n"
            )
            return True

        monkeypatch.setattr(weather, "download_published_file", fake_download)
        data = weather._read_station_csv(name)
        assert data["datetime"].to_list() == [date(2015, 1, 1)]


class TestSampleMinistryGrid:
    def test_samples_station_cells(self, monkeypatch, polygons):
        inventory = pl.DataFrame(
            {
                "climate_id": ["7060225"],
                "name": ["Pikauba"],
                "longitude": [-71.3],
                "latitude": [47.7],
                "start": [date(2015, 1, 1)],
                "end": [date(2015, 1, 3)],
            }
        )
        processed = make_processed_dataset(polygons, 2015)
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year, crs: processed if year == 2015 else None,
        )
        data = weather._sample_ministry_grid(
            inventory, range(2014, 2016), crs=crs
        )
        assert data["climate_id"].unique().to_list() == ["7060225"]
        # the 05:00 stamp collapses to the calendar date
        assert data["datetime"].to_list() == [
            datetime(2015, 1, 1),
            datetime(2015, 1, 2),
            datetime(2015, 1, 3),
        ]
        assert data["precipitation"].to_list() == [2.0, 2.0, 2.0]

    def test_no_year_available_returns_empty(self, monkeypatch):
        inventory = pl.DataFrame(
            {
                "climate_id": ["7060225"],
                "name": ["Pikauba"],
                "longitude": [-71.3],
                "latitude": [47.7],
                "start": [date(2015, 1, 1)],
                "end": [date(2015, 1, 3)],
            }
        )
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year, crs: None,
        )
        data = weather._sample_ministry_grid(
            inventory, range(2015, 2016), crs=crs
        )
        assert data.is_empty()
        assert data.schema == weather._empty_backfill_frame().schema


class TestSampleEra5Cells:
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

    def test_cached_cells_skip_credentials(
        self, tmp_data_dir, monkeypatch, inventory
    ):
        cell = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [-1.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        )
        path = weather._era5_cell_path(47.75, -71.25, 2015, 2016)
        path.parent.mkdir(exist_ok=True, parents=True)
        cell.write_ipc(path)
        check = MagicMock(side_effect=AssertionError("must not be called"))
        monkeypatch.setattr(weather, "_check_era5_credentials", check)
        data = weather._sample_era5_cells(inventory, 2015, 2016)
        assert data["climate_id"].to_list() == ["7060225"]
        assert data["precipitation"].to_list() == [1.0]

    def test_missing_cells_check_credentials(self, monkeypatch, inventory):
        check = MagicMock()
        monkeypatch.setattr(weather, "_check_era5_credentials", check)
        cell = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [-1.0],
            }
        )
        monkeypatch.setattr(
            weather,
            "_read_era5_cell",
            lambda lat, lon, start, end: cell,
        )
        weather._sample_era5_cells(inventory, 2015, 2016)
        check.assert_called_once()


class TestEra5Lattice:
    @pytest.mark.parametrize(
        ["value", "expected"],
        [(48.13, 48.25), (47.7, 47.75), (-71.3, -71.25), (-71.38, -71.5)],
    )
    def test_snaps_to_quarter_degree(self, value, expected):
        assert weather._era5_lattice(value) == expected


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
        # the centroid is taken in the projected crs, so the station must be
        # placed at that projected point sent back to lat/lon
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

    def test_truncates_to_n_stations(self, polygons):
        inventory = pl.DataFrame(
            {
                "climate_id": ["a", "b", "c"],
                "name": ["A", "B", "C"],
                "longitude": [-71.3, -71.2, -71.1],
                "latitude": [47.7, 47.7, 47.7],
                "start": [date(2015, 1, 1)] * 3,
                "end": [date(2017, 12, 31)] * 3,
            }
        )
        selection = weather._select_nearest_stations(polygons, inventory, 1)
        assert selection.group_by("id").len()["len"].to_list() == [1, 1]


class TestReadCompletedStation:
    def test_cache_hit(self, tmp_data_dir):
        cached = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
                "climate_id": ["7060225"],
            }
        )
        path = (
            tmp_data_dir
            / "raw"
            / "weather"
            / "stations_completed"
            / "7060225.ipc"
        )
        path.parent.mkdir(exist_ok=True, parents=True)
        cached.write_ipc(path)
        assert weather._read_completed_station("7060225").equals(cached)

    def test_builds_and_caches(
        self, tmp_data_dir, station_csvs, backfill_file
    ):
        completed = weather._read_completed_station("7060225")
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
        assert (
            tmp_data_dir
            / "raw"
            / "weather"
            / "stations_completed"
            / "7060225.ipc"
        ).exists()


class TestReadStationsBackfill:
    def test_missing_and_undownloadable_raises(self, monkeypatch):
        monkeypatch.setattr(
            weather, "download_published_file", lambda name: False
        )
        with pytest.raises(RuntimeError, match="holmes download"):
            weather._read_stations_backfill()


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


class TestNearestStationsGrid:
    def test_empty_polygons_return_empty_grid(
        self, station_csvs, empty_polygons
    ):
        grid = weather._nearest_stations_grid(
            empty_polygons.to_crs("EPSG:4326"), crs=crs
        )
        assert grid.is_empty()

    def test_full_pool_with_metadata(self, station_csvs, polygons):
        grid = weather._nearest_stations_grid(
            polygons.to_crs("EPSG:4326"), crs=crs
        )
        assert grid.filter(pl.col("id") == "061004").height == (
            weather.max_n_stations
        )
        row = grid.row(0, named=True)
        assert row["climate_id"] in weather.stations_files
        assert row["name"]
        assert row["start"] is not None
        point = shapely.from_geojson(row["geometry"])
        assert point.geom_type == "Point"


class TestReadEra5WeatherData:
    def test_empty_grid_returns_empty_frame(self, empty_polygons):
        data = weather._read_era5_weather_data(
            empty_polygons, 2015, 2016, crs=crs
        )
        assert data.is_empty()

    def test_weighted_mean_over_cells(self, monkeypatch, polygons):
        grid = pl.DataFrame(
            {
                "id": ["061004", "061004"],
                "latitude": [47.75, 48.0],
                "longitude": [-71.25, -71.25],
                "weight": [1.0, 3.0],
                "geometry": ["{}", "{}"],
                "climate_id": [None, None],
                "name": [None, None],
                "start": [None, None],
                "end": [None, None],
            },
            schema=weather._grid_schema(),
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
        monkeypatch.setattr(weather, "_era5_grid", lambda p, crs: grid)
        monkeypatch.setattr(
            weather,
            "_download_era5_cells",
            lambda cells, start, end: series,
        )
        data = weather._read_era5_weather_data(polygons, 2015, 2016, crs=crs)
        assert data["precipitation"].to_list() == [
            pytest.approx((1.0 * 1 + 5.0 * 3) / 4)
        ]
        assert data["temperature"].to_list() == [pytest.approx(3.0)]


class TestEra5Grid:
    def test_cells_cover_watersheds(self, polygons):
        grid = weather._era5_grid(polygons.to_crs("EPSG:4326"), crs=crs)
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
            weather._era5_grid(flat, crs=crs)


class TestEra5CellsCovering:
    def test_covers_bounds(self):
        cells = weather._era5_cells_covering((-71.3, 47.7, -71.2, 47.8))
        union = shapely.unary_union(cells)
        assert union.contains(shapely.box(-71.3, 47.7, -71.2, 47.8))
        for cell in cells:
            centre = cell.centroid
            assert round(centre.x / weather.era5_resolution, 6) % 1 == 0
            assert round(centre.y / weather.era5_resolution, 6) % 1 == 0


class TestDownloadEra5Cells:
    def test_cached_cells_skip_credentials(self, tmp_data_dir, monkeypatch):
        cells = pl.DataFrame({"latitude": [47.75], "longitude": [-71.25]})
        cached = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        )
        path = weather._era5_cell_path(47.75, -71.25, 2015, 2016)
        path.parent.mkdir(exist_ok=True, parents=True)
        cached.write_ipc(path)
        check = MagicMock(side_effect=AssertionError("must not be called"))
        monkeypatch.setattr(weather, "_check_era5_credentials", check)
        data = weather._download_era5_cells(cells, 2015, 2016)
        assert data.equals(cached)

    def test_missing_cells_check_credentials_once(self, monkeypatch):
        cells = pl.DataFrame(
            {"latitude": [47.75, 48.0], "longitude": [-71.25, -71.25]}
        )
        check = MagicMock()
        monkeypatch.setattr(weather, "_check_era5_credentials", check)
        cell = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
            }
        )
        monkeypatch.setattr(
            weather, "_read_era5_cell", lambda lat, lon, start, end: cell
        )
        data = weather._download_era5_cells(cells, 2015, 2016)
        check.assert_called_once()
        assert data.height == 2


class TestCheckEra5Credentials:
    def test_no_credentials_raises_with_instructions(self, monkeypatch):
        monkeypatch.setattr(
            weather.cdsapi,
            "Client",
            MagicMock(side_effect=Exception("no token")),
        )
        with pytest.raises(RuntimeError, match="cdsapirc"):
            weather._check_era5_credentials()

    def test_valid_credentials_pass(self, monkeypatch):
        monkeypatch.setattr(weather.cdsapi, "Client", MagicMock())
        weather._check_era5_credentials()


class TestReadEra5Cell:
    def test_cache_hit(self, tmp_data_dir):
        cached = pl.DataFrame(
            {
                "datetime": [datetime(2015, 1, 1)],
                "precipitation": [1.0],
                "temperature": [0.0],
                "latitude": [47.75],
                "longitude": [-71.25],
            }
        )
        path = weather._era5_cell_path(47.75, -71.25, 2015, 2016)
        path.parent.mkdir(exist_ok=True, parents=True)
        cached.write_ipc(path)
        assert weather._read_era5_cell(47.75, -71.25, 2015, 2016).equals(
            cached
        )

    def test_downloads_reduces_and_caches(self, tmp_data_dir, monkeypatch):
        raw = pl.DataFrame(
            {
                "valid_time": ["2015-01-01 12:00:00"],
                "tp": [0.001],
                "t2m": [273.15],
            }
        )
        monkeypatch.setattr(
            weather,
            "_download_era5_cell",
            lambda lat, lon, start, end: raw,
        )
        data = weather._read_era5_cell(47.75, -71.25, 2015, 2016)
        assert data["precipitation"].to_list() == [pytest.approx(1.0)]
        assert weather._era5_cell_path(47.75, -71.25, 2015, 2016).exists()


class TestDownloadEra5Cell:
    @staticmethod
    def make_client(files: dict[str, bytes]) -> MagicMock:
        def retrieve(dataset, request, archive):
            with zipfile.ZipFile(archive, "w") as z:
                for name, content in files.items():
                    z.writestr(name, content)

        client = MagicMock()
        client.retrieve.side_effect = retrieve
        return client

    def test_extracts_and_concats_csvs(self, monkeypatch):
        client = self.make_client(
            {
                "a.csv": b"valid_time,tp,t2m\n2015-01-01 00:00:00,0.001,273\n",
                "b.csv": b"valid_time,tp,t2m\n2015-01-01 01:00:00,0.002,274\n",
            }
        )
        monkeypatch.setattr(
            weather.cdsapi, "Client", MagicMock(return_value=client)
        )
        data = weather._download_era5_cell(47.75, -71.25, 2015, 2016)
        assert data.height == 2

    def test_zip_without_csv_raises(self, monkeypatch):
        client = self.make_client({"readme.txt": b"no data"})
        monkeypatch.setattr(
            weather.cdsapi, "Client", MagicMock(return_value=client)
        )
        with pytest.raises(ValueError, match="no csv"):
            weather._download_era5_cell(47.75, -71.25, 2015, 2016)


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


class TestReadMinistryGridWeatherData:
    def test_reduces_years_and_skips_missing(self, monkeypatch, polygons):
        processed = make_processed_dataset(polygons, 2015)
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year, crs: processed if year == 2015 else None,
        )
        data = weather._read_ministry_grid_weather_data(
            polygons, [2014, 2015], crs=crs
        )
        assert sorted(data["id"].unique()) == ["061004", "061020"]
        # constant field: the coverage-weighted mean is the constant
        assert data["precipitation"].to_list() == pytest.approx([2.0] * 6)
        assert data["temperature"].to_list() == pytest.approx([-3.0] * 6)

    def test_no_years_returns_typed_empty(self, monkeypatch, polygons):
        monkeypatch.setattr(
            weather, "_download_ministry_grid_files", lambda names: None
        )
        monkeypatch.setattr(
            weather,
            "_read_year_ministry_grid_weather_data",
            lambda year, crs: None,
        )
        data = weather._read_ministry_grid_weather_data(
            polygons, [2015], crs=crs
        )
        assert data.is_empty()
        assert data.columns == [
            "id",
            "datetime",
            "precipitation",
            "temperature",
        ]


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
        assert (
            weather._read_year_ministry_grid_weather_data(2015, crs=crs)
            is None
        )

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
        data = weather._read_year_ministry_grid_weather_data(2015, crs=crs)
        assert data is not None
        assert set(data.data_vars) == {"precipitation", "temperature"}
        assert data.rio.crs.to_string() == crs


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
        grid = weather._ministry_grid_grid(
            polygons.to_crs("EPSG:4326"), crs=crs
        )
        assert grid.is_empty()

    def test_single_cell_lattice_raises(
        self, tmp_data_dir, monkeypatch, polygons
    ):
        self.write_raster(tmp_data_dir, polygons, n=1)
        with pytest.raises(ValueError, match="too few cells"):
            weather._ministry_grid_grid(polygons.to_crs("EPSG:4326"), crs=crs)

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
            weather._ministry_grid_grid(outside, crs=crs)

    def test_cells_cover_watersheds(self, tmp_data_dir, polygons):
        self.write_raster(tmp_data_dir, polygons)
        grid = weather._ministry_grid_grid(
            polygons.to_crs("EPSG:4326"), crs=crs
        )
        assert set(grid["id"].unique()) == {"061004", "061020"}
        assert (grid["weight"] > 0).all()

    def test_zero_area_watershed_yields_empty_grid(
        self, tmp_data_dir, polygons
    ):
        # inside the lattice, so cells are found, but every intersection has
        # zero area and is skipped
        self.write_raster(tmp_data_dir, polygons)
        point = [(-71.3, 47.7)] * 3
        flat = gpd.GeoDataFrame(
            {"id": ["x"], "geometry": [shapely.Polygon(point)]},
            crs="EPSG:4326",
        )
        assert weather._ministry_grid_grid(flat, crs=crs).is_empty()


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


class TestDownloadMinistryGridFiles:
    def test_nothing_missing_returns_early(self, tmp_data_dir, monkeypatch):
        directory = tmp_data_dir / "raw" / "weather" / "ministry_grid"
        directory.mkdir(exist_ok=True, parents=True)
        (directory / "PREC_2015.nc").touch()
        download = MagicMock(side_effect=AssertionError("must not download"))
        monkeypatch.setattr(weather, "_ministry_grid_file", download)
        weather._download_ministry_grid_files(["PREC_2015.nc"])

    def test_downloads_missing_concurrently(self, monkeypatch):
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
            "get",
            lambda url, **kwargs: make_response(body),
        )
        path = weather._ministry_grid_file("PREC_2015.nc")
        assert path is not None
        assert path.exists()
        xr.open_dataset(path).close()

    def test_http_error_returns_none(self, tmp_data_dir, monkeypatch):
        resp = make_response(b"")
        resp.raise_for_status.side_effect = RuntimeError("503")
        monkeypatch.setattr(weather.httpx, "get", lambda url, **kwargs: resp)
        assert weather._ministry_grid_file("PREC_2015.nc") is None

    def test_corrupt_body_returns_none(self, tmp_data_dir, monkeypatch):
        monkeypatch.setattr(
            weather.httpx,
            "get",
            lambda url, **kwargs: make_response(b"<html>error</html>"),
        )
        assert weather._ministry_grid_file("PREC_2015.nc") is None
        assert not (
            tmp_data_dir / "raw" / "weather" / "ministry_grid" / "PREC_2015.nc"
        ).exists()


class TestCalculateMaskedMean:
    def test_masks_nan_and_empty_denominator(self):
        values = np.array(
            [
                [1.0, 3.0, 100.0],
                [np.nan, 3.0, 100.0],
                [np.nan, np.nan, 100.0],
            ]
        )
        cells = np.array([0, 1])
        weights = np.array([1.0, 1.0])
        means = weather._calculate_masked_mean(values, cells, weights)
        assert means[0] == pytest.approx(2.0)
        assert means[1] == pytest.approx(3.0)
        assert np.isnan(means[2])
