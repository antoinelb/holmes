import io
import zipfile
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import geopandas as gpd
import numpy as np
import polars as pl
import pyproj
import pytest
import shapely
import shapely.ops
import xarray as xr

import holmes.data.hydro as hydro


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


class TestGetStationData:
    async def test_cache_hit(self, tmp_data_dir, stations_df):
        path = tmp_data_dir / "raw" / "hydro" / "station_data.ipc"
        path.parent.mkdir(parents=True)
        stations_df.write_ipc(path)
        data = await hydro.get_station_data()
        assert data.equals(stations_df)

    async def test_cache_miss_joins_and_writes(
        self, tmp_data_dir, monkeypatch, raw_stations
    ):
        watersheds = pl.DataFrame(
            {
                "id": ["061004", "061022", "061028"],
                "geometry": [b"wkb1", b"wkb2", b"wkb3"],
            }
        )
        (tmp_data_dir / "raw" / "hydro").mkdir(parents=True)
        monkeypatch.setattr(hydro, "_get_stations", lambda: raw_stations)
        monkeypatch.setattr(
            hydro, "_get_watersheds", AsyncMock(return_value=watersheds)
        )
        data = await hydro.get_station_data()
        assert data["name"].to_list() == [
            "Aux Écorces",
            "Pikauba Amont",
            "Pikauba Aval",
        ]
        assert data["geometry"].to_list() == [b"wkb1", b"wkb2", b"wkb3"]
        assert (tmp_data_dir / "raw" / "hydro" / "station_data.ipc").exists()


class TestGetStations:
    def test_cache_hit(self, tmp_data_dir, raw_stations):
        path = tmp_data_dir / "raw" / "hydro" / "stations.ipc"
        path.parent.mkdir(parents=True)
        raw_stations.write_ipc(path)
        assert hydro._get_stations().equals(raw_stations)

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
        stations = hydro._get_stations()
        assert stations["id"].to_list() == ["061004"]
        assert stations["start"].to_list() == [1910]
        assert stations["open"].to_list() == [True]
        assert (tmp_data_dir / "raw" / "hydro" / "stations.ipc").exists()


class TestRenameStations:
    def test_hardcoded_names(self, raw_stations):
        renamed = hydro._rename_stations(raw_stations)
        assert renamed["name"].to_list() == [
            "Aux Écorces",
            "Pikauba Amont",
            "Pikauba Aval",
        ]


class TestGetWatersheds:
    async def test_cache_hit(self, tmp_data_dir):
        cached = pl.DataFrame({"id": ["061004"], "geometry": [b"wkb"]})
        path = tmp_data_dir / "raw" / "hydro" / "watersheds" / "watersheds.ipc"
        path.parent.mkdir(parents=True)
        cached.write_ipc(path)
        data = await hydro._get_watersheds(cached.select("id"))
        assert data.equals(cached)

    async def test_build_adds_geojson_and_dem(
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
        (tmp_data_dir / "raw" / "hydro" / "watersheds").mkdir(parents=True)
        monkeypatch.setattr(
            hydro, "_download_watersheds", AsyncMock(return_value=downloaded)
        )
        monkeypatch.setattr(
            hydro, "_get_dem_data", AsyncMock(return_value=dem)
        )
        data = await hydro._get_watersheds(raw_stations)
        assert data.height == 3
        row = data.filter(pl.col("id") == "061004")
        assert shapely.from_geojson(row[0, "geometry_geojson"]).equals(polygon)
        assert (
            data.filter(pl.col("id") == "061022")[0, "geometry_geojson"]
            is None
        )
        assert row[0, "elevation_layers"].to_list() == [300.0, 400.0]


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

    async def test_reads_existing_files(
        self, tmp_data_dir, monkeypatch, shapefiles
    ):
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
        watersheds = await hydro._download_watersheds()
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

    async def test_downloads_and_extracts_zips(
        self, tmp_data_dir, monkeypatch, shapefiles
    ):
        open_frame, closed_frame, _ = shapefiles

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("nested/data.shp", b"shp")
            archive.writestr("nested/data.dbf", b"dbf")
        zip_bytes = buffer.getvalue()

        resp = MagicMock(content=zip_bytes)
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(
            hydro.httpx, "AsyncClient", MagicMock(return_value=client)
        )
        monkeypatch.setattr(
            hydro.gpd,
            "read_file",
            lambda path: open_frame if "open" in str(path) else closed_frame,
        )
        watersheds = await hydro._download_watersheds()
        assert watersheds.height == 3
        base = tmp_data_dir / "raw" / "hydro" / "watersheds"
        for name in ["open", "closed"]:
            assert (base / name / "watersheds.shp").exists()
            assert (base / name / "watersheds.dbf").exists()
            assert not (base / name / "watersheds.zip").exists()
            assert not (base / name / "nested").exists()


class TestGetDemData:
    @pytest.fixture
    def watersheds(self):
        polygon = shapely.box(-71.4, 47.6, -71.2, 47.8)
        return pl.DataFrame(
            {"id": ["061004"], "geometry": [shapely.to_wkb(polygon)]}
        )

    async def test_invalid_n_bands_raises(self, watersheds):
        with pytest.raises(ValueError, match="n_bands"):
            await hydro._get_dem_data(watersheds, n_bands=0)

    async def test_cached_tiff_skips_download(
        self, tmp_data_dir, monkeypatch, watersheds
    ):
        (tmp_data_dir / "raw" / "hydro" / "dem").mkdir(parents=True)
        (tmp_data_dir / "raw" / "hydro" / "dem" / "061004.tiff").touch()
        download = MagicMock()
        monkeypatch.setattr(hydro, "_download_dem", download)
        monkeypatch.setattr(
            hydro, "_compute_dem_bands", lambda path, n: [300.0, 400.0]
        )
        bands = await hydro._get_dem_data(watersheds, n_bands=2)
        download.assert_not_called()
        assert bands["elevation_layers"].to_list() == [[300.0, 400.0]]

    async def test_missing_geometry_raises(self, tmp_data_dir):
        watersheds = pl.DataFrame(
            {"id": ["061004"], "geometry": [None]},
            schema={"id": pl.String, "geometry": pl.Binary},
        )
        with pytest.raises(RuntimeError, match="No watershed geometry"):
            await hydro._get_dem_data(watersheds)

    async def test_no_coverage_raises(
        self, tmp_data_dir, monkeypatch, watersheds
    ):
        def download(wkb, path):
            raise RuntimeError()

        monkeypatch.setattr(hydro, "_download_dem", download)
        with pytest.raises(RuntimeError, match="No DEM coverage"):
            await hydro._get_dem_data(watersheds)

    async def test_other_failure_raises(
        self, tmp_data_dir, monkeypatch, watersheds
    ):
        def download(wkb, path):
            raise ValueError("boom")

        monkeypatch.setattr(hydro, "_download_dem", download)
        with pytest.raises(RuntimeError, match="Failed DEM"):
            await hydro._get_dem_data(watersheds)

    async def test_downloads_then_computes(
        self, tmp_data_dir, monkeypatch, watersheds
    ):
        def download(wkb, path):
            path.touch()

        monkeypatch.setattr(hydro, "_download_dem", download)
        monkeypatch.setattr(
            hydro, "_compute_dem_bands", lambda path, n: [250.0] * n
        )
        bands = await hydro._get_dem_data(watersheds, n_bands=3)
        assert bands["elevation_layers"].to_list() == [[250.0, 250.0, 250.0]]


class TestDownloadDem:
    @pytest.fixture
    def wkb(self):
        return shapely.to_wkb(shapely.box(-71.4, 47.6, -71.2, 47.8))

    def test_no_hrefs_raises(self, monkeypatch, wkb, tmp_path):
        monkeypatch.setattr(hydro, "_find_dtm_hrefs", lambda bbox: [])
        with pytest.raises(RuntimeError):
            hydro._download_dem(wkb, tmp_path / "dem.tiff")

    def test_single_cog_skips_merge(self, monkeypatch, wkb, tmp_path):
        cog = MagicMock()
        cog.rio.clip_box.return_value = cog
        cog.rio.clip.return_value = cog
        monkeypatch.setattr(hydro, "_find_dtm_hrefs", lambda bbox: ["href"])
        monkeypatch.setattr(
            hydro.rioxarray, "open_rasterio", lambda href, masked: cog
        )
        merge = MagicMock()
        monkeypatch.setattr(hydro, "merge_arrays", merge)
        hydro._download_dem(wkb, tmp_path / "dem.tiff")
        merge.assert_not_called()
        cog.rio.to_raster.assert_called_once_with(tmp_path / "dem.tiff")

    def test_multiple_cogs_merge(self, monkeypatch, wkb, tmp_path):
        cog = MagicMock()
        cog.rio.clip_box.return_value = cog
        merged = MagicMock()
        merged.rio.clip.return_value = merged
        monkeypatch.setattr(hydro, "_find_dtm_hrefs", lambda bbox: ["a", "b"])
        monkeypatch.setattr(
            hydro.rioxarray, "open_rasterio", lambda href, masked: cog
        )
        merge = MagicMock(return_value=merged)
        monkeypatch.setattr(hydro, "merge_arrays", merge)
        hydro._download_dem(wkb, tmp_path / "dem.tiff")
        merge.assert_called_once()
        merged.rio.to_raster.assert_called_once()


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


class TestGetStreamflowData:
    async def test_cache_hit(self, tmp_data_dir, streamflow_df):
        cached = streamflow_df.filter(pl.col("id") == "061004")
        path = tmp_data_dir / "raw" / "hydro" / "streamflow" / "061004.ipc"
        path.parent.mkdir(parents=True)
        cached.write_ipc(path)
        data = await hydro.get_streamflow_data("061004")
        assert data.equals(cached)

    async def test_densifies_missing_days(self, tmp_data_dir, monkeypatch):
        sparse = pl.DataFrame(
            {
                "id": ["061004"] * 2,
                "datetime": [date(2020, 1, 1), date(2020, 1, 3)],
                "streamflow": [1.0, 3.0],
            }
        )
        monkeypatch.setattr(
            hydro, "_get_streamflow_data", AsyncMock(return_value=sparse)
        )
        data = await hydro.get_streamflow_data("061004")
        assert data["datetime"].to_list() == [
            date(2020, 1, 1),
            date(2020, 1, 2),
            date(2020, 1, 3),
        ]
        assert data["streamflow"].to_list() == [1.0, None, 3.0]
        assert (
            tmp_data_dir / "raw" / "hydro" / "streamflow" / "061004.ipc"
        ).exists()


class TestGetStreamflowDataParsing:
    @staticmethod
    def make_client(text: str) -> MagicMock:
        resp = MagicMock()
        resp.text = text
        client = MagicMock()
        client.get = AsyncMock(return_value=resp)
        return client

    async def test_parses_and_converts_units(self):
        text = (
            "Station: 061004\n"
            "Bassin versant: 500,5 km²\n"
            "061004 2020/01/01 1.5\n"
            "061004 2020/01/02 -0.5\n"
            "061004 2020/01/03\n"
            "some noise line\n"
        )
        client = self.make_client(text)
        data = await hydro._get_streamflow_data(client, "061004")
        assert data["datetime"].to_list() == [
            date(2020, 1, 1),
            date(2020, 1, 2),
            date(2020, 1, 3),
        ]
        assert data["streamflow"][0] == pytest.approx(1.5 * 86.4 / 500.5)
        assert data["streamflow"][1] == pytest.approx(-0.5 * 86.4 / 500.5)
        assert data["streamflow"][2] is None

    async def test_missing_header_raises(self):
        client = self.make_client("061004 2020/01/01 1.5\n")
        with pytest.raises(ValueError, match="No drainage area"):
            await hydro._get_streamflow_data(client, "061004")

    async def test_invalid_area_raises(self):
        client = self.make_client("Bassin versant: 0 km²\n")
        with pytest.raises(ValueError, match="Invalid drainage area"):
            await hydro._get_streamflow_data(client, "061004")
