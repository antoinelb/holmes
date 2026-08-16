import io
import os
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import geopandas as gpd
import httpx
import numpy as np
import polars as pl
import pyproj
import pytest
import shapely
import shapely.ops
import xarray as xr

import holmes.download.hydro as hydro


@pytest.fixture
def raw_stations() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": ["061004", "061022", "061028"],
            "name": ["Aux Écorces", "Old name", "Other name"],
            "type": ["Débit"] * 3,
            "lat": [47.7, 47.8, 47.9],
            "lon": [-71.3, -71.4, -71.5],
            "start": [2015, 2015, 2015],
            "end": [2017, 2017, 2017],
            "waterway": ["Rivière"] * 3,
            "area": [500.0, 400.0, 300.0],
            "open": [True, True, False],
        }
    )


def make_sync_client(monkeypatch, responses: list) -> MagicMock:
    """Patch `hydro.httpx.Client` with a mock yielding `responses`."""
    client = MagicMock()
    client.get = MagicMock(side_effect=responses)
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(hydro.httpx, "Client", MagicMock(return_value=client))
    return client


def backdate(path: Path) -> None:
    # a file written by a test is today's, which fetch_streamflow now
    # skips; ageing it by a day restores the "must refetch" case
    stamp = (datetime.now() - timedelta(days=1)).timestamp()
    os.utime(path, (stamp, stamp))


def streamflow_body(id: str) -> str:
    return (
        f"Station: {id}\n"
        "Bassin versant: 500,5 km²\n"
        f"{id} 2020/01/01 1.5\n"
        f"{id} 2020/01/03 3.0\n"
        "some noise line\n"
    )


class TestBuildStationData:
    def test_skip_if_exists(self, tmp_data_dir, stations_df):
        path = tmp_data_dir / "raw" / "hydro" / "station_data.ipc"
        path.parent.mkdir(parents=True)
        stations_df.write_ipc(path)
        data = hydro.build_station_data()
        assert data.equals(stations_df)

    def test_cache_miss_joins_and_writes(
        self, tmp_data_dir, monkeypatch, raw_stations
    ):
        watersheds = pl.DataFrame(
            {
                "id": ["061004", "061022", "061028"],
                "geometry": [b"wkb1", b"wkb2", b"wkb3"],
            }
        )
        monkeypatch.setattr(
            hydro, "_get_stations", lambda *, force: raw_stations
        )
        monkeypatch.setattr(
            hydro, "_get_watersheds", lambda stations, *, force: watersheds
        )
        data = hydro.build_station_data()
        assert data["name"].to_list() == [
            "Aux Écorces",
            "Pikauba Amont",
            "Pikauba Aval",
        ]
        assert data["geometry"].to_list() == [b"wkb1", b"wkb2", b"wkb3"]
        path = tmp_data_dir / "raw" / "hydro" / "station_data.ipc"
        assert path.exists()
        # the staged write leaves no partial file behind
        assert not list(path.parent.glob("*.part"))

    def test_force_rebuilds_every_stage(
        self, tmp_data_dir, monkeypatch, raw_stations
    ):
        path = tmp_data_dir / "raw" / "hydro" / "station_data.ipc"
        path.parent.mkdir(parents=True)
        pl.DataFrame({"id": ["stale"]}).write_ipc(path)
        watersheds = pl.DataFrame(
            {"id": ["061004", "061022", "061028"], "geometry": [b"w"] * 3}
        )
        forces = []

        def get_stations(*, force):
            forces.append(force)
            return raw_stations

        def get_watersheds(stations, *, force):
            forces.append(force)
            return watersheds

        monkeypatch.setattr(hydro, "_get_stations", get_stations)
        monkeypatch.setattr(hydro, "_get_watersheds", get_watersheds)
        data = hydro.build_station_data(force=True)
        assert forces == [True, True]
        assert "stale" not in data["id"].to_list()
        assert "stale" not in pl.read_ipc(path, memory_map=False)["id"]


class TestGetStations:
    def test_cache_hit(self, tmp_data_dir, raw_stations):
        path = tmp_data_dir / "raw" / "hydro" / "stations.ipc"
        path.parent.mkdir(parents=True)
        raw_stations.write_ipc(path)
        assert hydro._get_stations(force=False).equals(raw_stations)

    def test_download_renames_and_filters(self, tmp_data_dir, monkeypatch):
        source = pl.DataFrame(
            {
                "no": ["061004", "999999"],
                "nom": ["Aux Écorces", "Elsewhere"],
                "type": ["Débit", "Débit"],
                "latitude": [47.7, 50.0],
                "longitude": [-71.3, -60.0],
                "debut": ["1910", "x"],
                "fin": ["2017", "2020"],
                "cours_eau": ["Rivière", "Fleuve"],
                "superficie": [500.0, 100.0],
                "etat": ["Ouverte", "Fermée"],
            }
        )
        monkeypatch.setattr(hydro.pl, "read_csv", lambda url, **kwargs: source)
        stations = hydro._get_stations(force=False)
        assert stations["id"].to_list() == ["061004"]
        assert stations["start"].to_list() == [1910]
        assert stations["open"].to_list() == [True]
        assert (tmp_data_dir / "raw" / "hydro" / "stations.ipc").exists()

    def test_force_redownloads(self, tmp_data_dir, monkeypatch, raw_stations):
        path = tmp_data_dir / "raw" / "hydro" / "stations.ipc"
        path.parent.mkdir(parents=True)
        pl.DataFrame({"id": ["stale"]}).write_ipc(path)
        source = pl.DataFrame(
            {
                "no": ["061004"],
                "nom": ["Aux Écorces"],
                "type": ["Débit"],
                "latitude": [47.7],
                "longitude": [-71.3],
                "debut": ["1910"],
                "fin": ["2017"],
                "cours_eau": ["Rivière"],
                "superficie": [500.0],
                "etat": ["Ouverte"],
            }
        )
        monkeypatch.setattr(hydro.pl, "read_csv", lambda url, **kwargs: source)
        stations = hydro._get_stations(force=True)
        assert stations["id"].to_list() == ["061004"]


class TestRenameStations:
    def test_hardcoded_names(self, raw_stations):
        renamed = hydro._rename_stations(raw_stations)
        assert renamed["name"].to_list() == [
            "Aux Écorces",
            "Pikauba Amont",
            "Pikauba Aval",
        ]


class TestGetWatersheds:
    def test_cache_hit(self, tmp_data_dir):
        cached = pl.DataFrame({"id": ["061004"], "geometry": [b"wkb"]})
        path = tmp_data_dir / "raw" / "hydro" / "watersheds" / "watersheds.ipc"
        path.parent.mkdir(parents=True)
        cached.write_ipc(path)
        data = hydro._get_watersheds(cached.select("id"), force=False)
        assert data.equals(cached)

    def test_build_adds_geojson_and_dem(
        self, tmp_data_dir, monkeypatch, raw_stations
    ):
        polygon = shapely.box(-71.4, 47.6, -71.2, 47.8)
        downloaded = pl.DataFrame(
            {
                "id": ["061004", "061022"],
                "geometry": [shapely.to_wkb(polygon), None],
            }
        )
        dem = pl.DataFrame(
            {"id": ["061004"], "elevation_layers": [[300.0, 400.0]]},
            schema={
                "id": pl.String,
                "elevation_layers": pl.List(pl.Float64),
            },
        )
        monkeypatch.setattr(
            hydro, "_download_watersheds", lambda *, force: downloaded
        )
        monkeypatch.setattr(hydro, "_get_dem_data", lambda data, *, force: dem)
        data = hydro._get_watersheds(raw_stations, force=False)
        assert data.height == 3
        row = data.filter(pl.col("id") == "061004")
        assert shapely.from_wkb(row[0, "geometry"]).equals(polygon)
        assert data.filter(pl.col("id") == "061022")[0, "geometry"] is None
        # the geojson copy is derived by the server, never stored
        assert "geometry_geojson" not in data.columns
        assert row[0, "elevation_layers"].to_list() == [300.0, 400.0]
        assert (
            tmp_data_dir / "raw" / "hydro" / "watersheds" / "watersheds.ipc"
        ).exists()


class TestDownloadWatersheds:
    @pytest.fixture
    def shapefiles(self):
        # closed geometries live in EPSG:32198, open in EPSG:4269
        to_lambert = pyproj.Transformer.from_crs(
            "EPSG:4326", "EPSG:32198", always_xy=True
        ).transform
        open_polygon = shapely.box(-71.4, 47.6, -71.2, 47.8)
        closed_polygon = shapely.ops.transform(
            to_lambert, shapely.box(-71.6, 47.5, -71.5, 47.7)
        )
        open_frame = gpd.GeoDataFrame(
            {
                "Station": ["061004", "061004", "061021"],
                "Sup_Diffus": [500.0, 100.0, 300.0],
            },
            geometry=[
                open_polygon,
                shapely.box(-71.3, 47.6, -71.2, 47.7),
                None,
            ],
        )
        closed_frame = gpd.GeoDataFrame(
            {"tp": ["061022"], "Sup_Km": [400.0]},
            geometry=[closed_polygon],
        )
        return open_frame, closed_frame, open_polygon

    @staticmethod
    def make_zip_bytes() -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("nested/data.shp", b"shp")
            archive.writestr("nested/data.dbf", b"dbf")
        return buffer.getvalue()

    def test_reads_existing_files(self, tmp_data_dir, monkeypatch, shapefiles):
        open_frame, closed_frame, open_polygon = shapefiles
        base = tmp_data_dir / "raw" / "hydro" / "watersheds"
        for name in ["open", "closed"]:
            (base / name).mkdir(parents=True)
            (base / name / "watersheds.shp").touch()
        monkeypatch.setattr(
            hydro.gpd,
            "read_file",
            lambda path: open_frame if "open" in str(path) else closed_frame,
        )
        watersheds = hydro._download_watersheds(force=False)
        assert sorted(watersheds["id"].to_list()) == [
            "061004",
            "061021",
            "061022",
        ]
        # dedup keeps the largest area; NAD83→WGS84 is numerically ~identity
        kept = shapely.from_wkb(
            watersheds.filter(pl.col("id") == "061004")[0, "geometry"]
        )
        assert kept.equals_exact(open_polygon, tolerance=1e-6)
        # the closed polygon comes back from EPSG:32198 to lat/lon
        closed = shapely.from_wkb(
            watersheds.filter(pl.col("id") == "061022")[0, "geometry"]
        )
        assert closed.centroid.x == pytest.approx(-71.55, abs=1e-3)
        assert closed.centroid.y == pytest.approx(47.6, abs=1e-3)
        # a null geometry stays null
        assert (
            watersheds.filter(pl.col("id") == "061021")[0, "geometry"] is None
        )

    def test_downloads_and_extracts_zips(
        self, tmp_data_dir, monkeypatch, shapefiles
    ):
        open_frame, closed_frame, _ = shapefiles
        zip_bytes = self.make_zip_bytes()
        make_sync_client(monkeypatch, [MagicMock(content=zip_bytes)] * 2)
        monkeypatch.setattr(
            hydro.gpd,
            "read_file",
            lambda path: open_frame if "open" in str(path) else closed_frame,
        )
        watersheds = hydro._download_watersheds(force=False)
        assert watersheds.height == 3
        base = tmp_data_dir / "raw" / "hydro" / "watersheds"
        for name in ["open", "closed"]:
            assert (base / name / "watersheds.shp").exists()
            assert (base / name / "watersheds.dbf").exists()
            assert not (base / name / "watersheds.zip").exists()
            assert not (base / name / "nested").exists()

    def test_force_removes_stale_extraction(
        self, tmp_data_dir, monkeypatch, shapefiles
    ):
        open_frame, closed_frame, _ = shapefiles
        base = tmp_data_dir / "raw" / "hydro" / "watersheds"
        for name in ["open", "closed"]:
            (base / name).mkdir(parents=True)
            (base / name / "watersheds.shp").touch()
            (base / name / "stale.txt").touch()
        zip_bytes = self.make_zip_bytes()
        make_sync_client(monkeypatch, [MagicMock(content=zip_bytes)] * 2)
        monkeypatch.setattr(
            hydro.gpd,
            "read_file",
            lambda path: open_frame if "open" in str(path) else closed_frame,
        )
        watersheds = hydro._download_watersheds(force=True)
        assert watersheds.height == 3
        for name in ["open", "closed"]:
            assert (base / name / "watersheds.shp").exists()
            assert not (base / name / "stale.txt").exists()


class TestGetDemData:
    @pytest.fixture
    def watersheds(self):
        polygon = shapely.box(-71.4, 47.6, -71.2, 47.8)
        return pl.DataFrame(
            {"id": ["061004"], "geometry": [shapely.to_wkb(polygon)]}
        )

    def test_invalid_n_bands_raises(self, watersheds):
        with pytest.raises(ValueError, match="n_bands"):
            hydro._get_dem_data(watersheds, n_bands=0)

    def test_cached_tiff_skips_download(
        self, tmp_data_dir, monkeypatch, watersheds
    ):
        (tmp_data_dir / "raw" / "hydro" / "dem").mkdir(parents=True)
        (tmp_data_dir / "raw" / "hydro" / "dem" / "061004.tiff").touch()
        download = MagicMock()
        monkeypatch.setattr(hydro, "_download_dem", download)
        monkeypatch.setattr(
            hydro, "_compute_dem_bands", lambda path, n: [300.0, 400.0]
        )
        bands = hydro._get_dem_data(watersheds, n_bands=2)
        download.assert_not_called()
        assert bands["elevation_layers"].to_list() == [[300.0, 400.0]]

    def test_force_redownloads_cached_tiff(
        self, tmp_data_dir, monkeypatch, watersheds
    ):
        (tmp_data_dir / "raw" / "hydro" / "dem").mkdir(parents=True)
        (tmp_data_dir / "raw" / "hydro" / "dem" / "061004.tiff").touch()
        download = MagicMock()
        monkeypatch.setattr(hydro, "_download_dem", download)
        monkeypatch.setattr(
            hydro, "_compute_dem_bands", lambda path, n: [300.0, 400.0]
        )
        hydro._get_dem_data(watersheds, n_bands=2, force=True)
        download.assert_called_once()

    def test_missing_geometry_raises(self, tmp_data_dir):
        watersheds = pl.DataFrame(
            {"id": ["061004"], "geometry": [None]},
            schema={"id": pl.String, "geometry": pl.Binary},
        )
        with pytest.raises(RuntimeError, match="No watershed geometry"):
            hydro._get_dem_data(watersheds)

    def test_no_coverage_raises(self, tmp_data_dir, monkeypatch, watersheds):
        def download(wkb, path):
            raise hydro._NoDemCoverageError()

        monkeypatch.setattr(hydro, "_download_dem", download)
        with pytest.raises(RuntimeError, match="No DEM coverage"):
            hydro._get_dem_data(watersheds)

    def test_other_failure_raises(self, tmp_data_dir, monkeypatch, watersheds):
        def download(wkb, path):
            raise ValueError("boom")

        monkeypatch.setattr(hydro, "_download_dem", download)
        with pytest.raises(RuntimeError, match="Failed DEM"):
            hydro._get_dem_data(watersheds)

    def test_unrelated_runtime_error_is_not_relabeled(
        self, tmp_data_dir, monkeypatch, watersheds
    ):
        # a RuntimeError from the raster stack must not pass as missing
        # coverage
        def download(wkb, path):
            raise RuntimeError("raster stack blew up")

        monkeypatch.setattr(hydro, "_download_dem", download)
        with pytest.raises(RuntimeError, match="Failed DEM"):
            hydro._get_dem_data(watersheds)

    def test_downloads_then_computes(
        self, tmp_data_dir, monkeypatch, watersheds
    ):
        def download(wkb, path):
            path.touch()

        monkeypatch.setattr(hydro, "_download_dem", download)
        monkeypatch.setattr(
            hydro, "_compute_dem_bands", lambda path, n: [250.0] * n
        )
        bands = hydro._get_dem_data(watersheds, n_bands=3)
        assert bands["elevation_layers"].to_list() == [[250.0, 250.0, 250.0]]


class TestDownloadDem:
    @pytest.fixture
    def wkb(self):
        return shapely.to_wkb(shapely.box(-71.4, 47.6, -71.2, 47.8))

    @staticmethod
    def touch_raster(mock: MagicMock) -> None:
        mock.rio.to_raster.side_effect = lambda path: Path(path).touch()

    def test_no_hrefs_raises(self, monkeypatch, wkb, tmp_path):
        monkeypatch.setattr(hydro, "_find_dtm_hrefs", lambda bbox: [])
        with pytest.raises(RuntimeError):
            hydro._download_dem(wkb, tmp_path / "dem.tiff")

    def test_single_cog_skips_merge(self, monkeypatch, wkb, tmp_path):
        cog = MagicMock()
        cog.rio.clip_box.return_value = cog
        cog.rio.clip.return_value = cog
        self.touch_raster(cog)
        monkeypatch.setattr(hydro, "_find_dtm_hrefs", lambda bbox: ["href"])
        monkeypatch.setattr(
            hydro.rioxarray, "open_rasterio", lambda href, masked: cog
        )
        merge = MagicMock()
        monkeypatch.setattr(hydro, "merge_arrays", merge)
        hydro._download_dem(wkb, tmp_path / "dem.tiff")
        merge.assert_not_called()
        cog.rio.to_raster.assert_called_once_with(tmp_path / "dem.part.tiff")
        # the staged raster is swapped in atomically
        assert (tmp_path / "dem.tiff").exists()
        assert not (tmp_path / "dem.part.tiff").exists()

    def test_multiple_cogs_merge(self, monkeypatch, wkb, tmp_path):
        cog = MagicMock()
        cog.rio.clip_box.return_value = cog
        merged = MagicMock()
        merged.rio.clip.return_value = merged
        self.touch_raster(merged)
        monkeypatch.setattr(hydro, "_find_dtm_hrefs", lambda bbox: ["a", "b"])
        monkeypatch.setattr(
            hydro.rioxarray, "open_rasterio", lambda href, masked: cog
        )
        merge = MagicMock(return_value=merged)
        monkeypatch.setattr(hydro, "merge_arrays", merge)
        hydro._download_dem(wkb, tmp_path / "dem.tiff")
        merge.assert_called_once()
        merged.rio.to_raster.assert_called_once()
        assert (tmp_path / "dem.tiff").exists()


class TestComputeDemBands:
    def test_quantiles_skip_nan(self, monkeypatch, tmp_path):
        values = np.array([[np.nan, 100.0], [200.0, 300.0]])
        da = xr.DataArray(values)
        monkeypatch.setattr(
            hydro.rioxarray, "open_rasterio", lambda path, masked: da
        )
        bands = hydro._compute_dem_bands(tmp_path / "dem.tiff", 2)
        assert bands == [
            pytest.approx(np.nanquantile(values, 0.25)),
            pytest.approx(np.nanquantile(values, 0.75)),
        ]


class TestFindDtmHrefs:
    def test_returns_dtm_assets_only(self, monkeypatch):
        with_dtm = MagicMock()
        with_dtm.assets = {"dtm": SimpleNamespace(href="https://cog/dtm.tif")}
        without = MagicMock()
        without.assets = {"dsm": SimpleNamespace(href="https://cog/dsm.tif")}
        search = MagicMock()
        search.items.return_value = [with_dtm, without]
        client = MagicMock()
        client.search.return_value = search
        monkeypatch.setattr(
            hydro.Client, "open", MagicMock(return_value=client)
        )
        assert hydro._find_dtm_hrefs([-71.4, 47.6, -71.2, 47.8]) == [
            "https://cog/dtm.tif"
        ]


class TestFetchStreamflow:
    def test_invalid_stations_raise(self, stations_df):
        with pytest.raises(ValueError, match="No stations"):
            hydro.fetch_streamflow(stations_df.head(0))
        with pytest.raises(ValueError, match="No stations"):
            hydro.fetch_streamflow(pl.DataFrame({"x": ["a"]}))

    def test_fetches_converts_and_writes(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        responses = [
            MagicMock(text=streamflow_body(id)) for id in stations_df["id"]
        ]
        make_sync_client(monkeypatch, responses)
        hydro.fetch_streamflow(stations_df)
        directory = tmp_data_dir / "raw" / "hydro" / "streamflow"
        for id in stations_df["id"]:
            data = pl.read_ipc(directory / f"{id}.ipc", memory_map=False)
            # densified onto a daily grid with explicit nulls
            assert data["datetime"].to_list() == [
                date(2020, 1, 1),
                date(2020, 1, 2),
                date(2020, 1, 3),
            ]
            # m³/s → mm/day via the header drainage area (500,5 km²)
            assert data["streamflow"][0] == pytest.approx(1.5 * 86.4 / 500.5)
            assert data["streamflow"][1] is None
            assert data["streamflow"][2] == pytest.approx(3.0 * 86.4 / 500.5)
        # the staged writes leave no partial file behind
        assert not list(directory.glob("*.part"))

    def test_skips_files_already_fetched_today(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        directory = tmp_data_dir / "raw" / "hydro" / "streamflow"
        directory.mkdir(parents=True)
        for id in stations_df["id"]:
            (directory / f"{id}.ipc").write_bytes(b"today")
        client = make_sync_client(monkeypatch, [])
        hydro.fetch_streamflow(stations_df)
        client.get.assert_not_called()
        for id in stations_df["id"]:
            assert (directory / f"{id}.ipc").read_bytes() == b"today"

    def test_force_refetches_a_file_from_today(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        directory = tmp_data_dir / "raw" / "hydro" / "streamflow"
        directory.mkdir(parents=True)
        for id in stations_df["id"]:
            (directory / f"{id}.ipc").write_bytes(b"today")
        make_sync_client(
            monkeypatch,
            [MagicMock(text=streamflow_body(id)) for id in stations_df["id"]],
        )
        hydro.fetch_streamflow(stations_df, force=True)
        for id in stations_df["id"]:
            assert (directory / f"{id}.ipc").read_bytes() != b"today"

    def test_failure_with_previous_file_warns_and_keeps_it(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        directory = tmp_data_dir / "raw" / "hydro" / "streamflow"
        directory.mkdir(parents=True)
        old = pl.DataFrame(
            {
                "id": ["061004"],
                "datetime": [date(2019, 1, 1)],
                "streamflow": [1.0],
            }
        )
        old.write_ipc(directory / "061004.ipc")
        backdate(directory / "061004.ipc")
        make_sync_client(
            monkeypatch,
            [
                httpx.HTTPError("down"),
                MagicMock(text=streamflow_body("061020")),
            ],
        )
        warnings = []
        monkeypatch.setattr(hydro, "warn_print", warnings.append)
        hydro.fetch_streamflow(stations_df)
        # the old file is untouched and the failure was warned about
        assert pl.read_ipc(directory / "061004.ipc", memory_map=False).equals(
            old
        )
        assert len(warnings) == 1
        assert "061004" in warnings[0]
        # the other station is unaffected by the failure
        assert (directory / "061020.ipc").exists()

    def test_parse_failure_with_previous_file_warns_and_keeps_it(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        directory = tmp_data_dir / "raw" / "hydro" / "streamflow"
        directory.mkdir(parents=True)
        old = pl.DataFrame(
            {
                "id": ["061004"],
                "datetime": [date(2019, 1, 1)],
                "streamflow": [1.0],
            }
        )
        old.write_ipc(directory / "061004.ipc")
        backdate(directory / "061004.ipc")
        # the row matches the regex but is not a real date, so the failure
        # surfaces as a polars error rather than a ValueError
        bad_body = "Bassin versant: 500,5 km²\n061004 2020/13/45 1.5\n"
        make_sync_client(
            monkeypatch,
            [
                MagicMock(text=bad_body),
                MagicMock(text=streamflow_body("061020")),
            ],
        )
        warnings = []
        monkeypatch.setattr(hydro, "warn_print", warnings.append)
        hydro.fetch_streamflow(stations_df)
        assert pl.read_ipc(directory / "061004.ipc", memory_map=False).equals(
            old
        )
        assert len(warnings) == 1
        assert "061004" in warnings[0]

    def test_failure_without_previous_file_raises(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        make_sync_client(monkeypatch, [httpx.HTTPError("down")])
        with pytest.raises(RuntimeError, match="no previous file"):
            hydro.fetch_streamflow(stations_df)
        directory = tmp_data_dir / "raw" / "hydro" / "streamflow"
        assert not list(directory.glob("*.ipc"))


class TestFetchStationStreamflow:
    @staticmethod
    def make_client(text: str) -> MagicMock:
        resp = MagicMock()
        resp.text = text
        client = MagicMock()
        client.get = MagicMock(return_value=resp)
        return client

    def test_parses_and_converts_units(self):
        client = self.make_client(streamflow_body("061004"))
        data = hydro._fetch_station_streamflow(client, "061004")
        assert data.columns == ["id", "datetime", "streamflow"]
        assert data["streamflow"][0] == pytest.approx(1.5 * 86.4 / 500.5)

    def test_missing_header_raises(self):
        client = self.make_client("061004 2020/01/01 1.5\n")
        with pytest.raises(ValueError, match="No drainage area"):
            hydro._fetch_station_streamflow(client, "061004")

    def test_invalid_area_raises(self):
        client = self.make_client("Bassin versant: 0 km²\n")
        with pytest.raises(ValueError, match="Invalid drainage area"):
            hydro._fetch_station_streamflow(client, "061004")

    def test_no_rows_raises(self):
        client = self.make_client("Bassin versant: 500,5 km²\n")
        with pytest.raises(ValueError, match="No streamflow rows"):
            hydro._fetch_station_streamflow(client, "061004")
