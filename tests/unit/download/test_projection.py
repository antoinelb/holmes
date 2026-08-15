import asyncio
import struct
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import polars as pl
import pyproj
import pytest
import xarray as xr

import holmes.download.geometry as geometry
import holmes.download.projection as projection

# CF sets lon_0 = pole longitude + 180, so 180 is the true identity
identity_pole = {
    "grid_mapping_name": "rotated_latitude_longitude",
    "grid_north_pole_latitude": 90.0,
    "grid_north_pole_longitude": 180.0,
    "north_pole_grid_longitude": 0.0,
}


def make_grid(
    *,
    start: int = 0,
    end: int = 2,
    n_times: int = 3,
    members: list[str] | None = None,
) -> projection._GridMetadata:
    return projection._GridMetadata(
        start=start,
        end=end,
        n_times=n_times,
        datetimes=[
            datetime(2020, 1, 1) + timedelta(days=day)
            for day in range(end - start + 1)
        ],
        members=members or [],
        # an identity rotated pole keeps rlat/rlon equal to lat/lon, so the
        # station polygons land on the lattice without hand-rotating them
        rlat=np.arange(47.35, 48.75, 0.1),
        rlon=np.arange(-71.85, -70.35, 0.1),
        crs=pyproj.CRS.from_cf(identity_pole),
    )


def make_dods(values: np.ndarray) -> bytes:
    dims = "".join(f"[dim{i} = {n}]" for i, n in enumerate(values.shape))
    header = f"Dataset {{ Float32 var{dims}; }} data;".encode()
    n = values.size
    return (
        header
        + b"\nData:\n"
        + struct.pack(">II", n, n)
        + values.astype(">f4").tobytes()
    )


def make_response(
    *, text: str = "", content: bytes = b"", error: Exception | None = None
) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.content = content
    if error is not None:
        resp.raise_for_status.side_effect = error
    return resp


def make_client(responses: list[MagicMock]) -> MagicMock:
    client = MagicMock()
    client.get = AsyncMock(side_effect=responses)
    return client


def espo_url(model: str, scenario: str) -> str:
    return (
        f"day_ESPO-G6-R2_v1.0.0_CMIP6_ScenarioMIP_NAM_Inst_{model}_"
        f"{scenario}_r1i1p1f1_19500101-21001231.ncml"
    )


def catalog_xml(entries: list[tuple[str, str]]) -> str:
    return "\n".join(
        f'<dataset urlPath="{espo_url(model, scenario)}"/>'
        for model, scenario in entries
    )


def write_product(id_: str, member: str) -> pl.DataFrame:
    data = pl.DataFrame(
        {
            "id": [id_],
            "ensemble": ["ClimEx"],
            "scenario": ["rcp8.5"],
            "member": [member],
            "datetime": [datetime(2020, 1, 1)],
            "precipitation": [1.0],
            "temperature": [0.0],
        }
    )
    path = projection._product_path(id_)
    path.parent.mkdir(exist_ok=True, parents=True)
    data.write_ipc(path)
    return data


class TestBuildProjectionData:
    def test_empty_stations_raises(self, stations_df):
        with pytest.raises(ValueError, match="No stations"):
            projection.build_projection_data(stations_df.head(0))

    def test_skip_when_all_present(
        self, tmp_data_dir, monkeypatch, stations_df
    ):
        for id_ in stations_df["id"]:
            write_product(id_, "r1")
        build = MagicMock()
        monkeypatch.setattr(projection, "_build_products", build)
        projection.build_projection_data(stations_df)
        build.assert_not_called()

    def test_builds_only_missing(self, tmp_data_dir, monkeypatch, stations_df):
        write_product("061004", "r1")
        calls = []

        async def fake_build(stations, *, rebuild):
            calls.append((stations["id"].to_list(), rebuild))

        monkeypatch.setattr(projection, "_build_products", fake_build)
        projection.build_projection_data(stations_df)
        assert calls == [(["061020"], False)]

    def test_force_rebuilds_all(self, tmp_data_dir, monkeypatch, stations_df):
        for id_ in stations_df["id"]:
            write_product(id_, "r1")
        calls = []

        async def fake_build(stations, *, rebuild):
            calls.append((stations["id"].to_list(), rebuild))

        monkeypatch.setattr(projection, "_build_products", fake_build)
        projection.build_projection_data(stations_df, force=True)
        assert calls == [(stations_df["id"].to_list(), True)]


class TestBuildProducts:
    @pytest.fixture
    def catalog(self) -> dict[str, list[tuple[str, str]]]:
        return {
            "ssp2-4.5": [("CanESM5", "https://espo/canesm5-245")],
            "ssp3-7.0": [("CanESM5", "https://espo/canesm5-370")],
        }

    def patch_pipeline(self, monkeypatch, catalog, members: list[str]):
        grid = make_grid(members=members)
        monkeypatch.setattr(
            projection,
            "_read_espo_catalog",
            AsyncMock(return_value=catalog),
        )
        monkeypatch.setattr(
            projection, "_read_grid_metadata", lambda url: grid
        )
        weights = {
            "061004": (np.array([0]), np.array([1.0])),
            "061020": (np.array([1]), np.array([1.0])),
        }
        monkeypatch.setattr(
            projection,
            "_station_weights",
            lambda stations, grid: (((0, 1), (0, 1)), weights),
        )
        return grid

    async def test_wrong_member_count_raises(
        self, monkeypatch, stations_df, catalog
    ):
        self.patch_pipeline(monkeypatch, catalog, members=["r1", "r2"])
        with pytest.raises(ValueError, match="ClimEx members"):
            await projection._build_products(stations_df, rebuild=False)

    async def test_assembles_products(
        self, tmp_data_dir, monkeypatch, stations_df, catalog
    ):
        members = ["r1", "r2"]
        self.patch_pipeline(monkeypatch, catalog, members=members)
        monkeypatch.setattr(projection, "n_members", len(members))

        async def fake_read_member(
            semaphore, client, task, grid, box, weights, *, rebuild
        ):
            for id_ in weights:
                path = projection._member_path(id_, task.scenario, task.member)
                path.parent.mkdir(exist_ok=True, parents=True)
                pl.DataFrame(
                    {
                        "id": [id_],
                        "scenario": [task.scenario],
                        "member": [task.member],
                        "datetime": [datetime(2020, 1, 1)],
                        "precipitation": [1.0],
                        "temperature": [0.0],
                    }
                ).write_ipc(path)

        monkeypatch.setattr(projection, "_read_member", fake_read_member)
        await projection._build_products(stations_df, rebuild=False)

        for id_ in stations_df["id"]:
            product = pl.read_ipc(
                projection._product_path(id_), memory_map=False
            )
            assert product.columns == [
                "id",
                "ensemble",
                "scenario",
                "member",
                "datetime",
                "precipitation",
                "temperature",
            ]
            assert set(product["ensemble"].unique()) == {
                "ClimEx",
                "ESPO-G6-R2",
            }
            assert (
                product.filter(pl.col("ensemble") == "ClimEx")["member"]
                .sort()
                .to_list()
                == members
            )
        # the staged writes leave no partial file behind
        projection_dir = tmp_data_dir / "raw" / "projection"
        assert not list(projection_dir.rglob("*.part"))

    async def test_failed_member_cancels_the_rest(
        self, monkeypatch, stations_df, catalog
    ):
        members = ["r1", "r2"]
        self.patch_pipeline(monkeypatch, catalog, members=members)
        monkeypatch.setattr(projection, "n_members", len(members))
        started = asyncio.Event()

        async def fake_read_member(
            semaphore, client, task, grid, box, weights, *, rebuild
        ):
            if task.member == "r1":
                started.set()
                raise RuntimeError("member failed")
            await asyncio.Event().wait()

        monkeypatch.setattr(projection, "_read_member", fake_read_member)
        with pytest.raises(RuntimeError, match="member failed"):
            await projection._build_products(stations_df, rebuild=False)
        assert started.is_set()


class TestReadEspoCatalog:
    async def test_success_first_attempt(self):
        xml = catalog_xml([("CanESM5", "ssp245"), ("CanESM5", "ssp370")])
        client = make_client([make_response(text=xml)])
        catalog = await projection._read_espo_catalog(client)
        assert list(catalog) == ["ssp2-4.5", "ssp3-7.0"]

    async def test_retries_http_error(self, no_sleep):
        xml = catalog_xml([("CanESM5", "ssp245"), ("CanESM5", "ssp370")])
        client = make_client(
            [
                make_response(error=projection.httpx.HTTPError("boom")),
                make_response(text=xml),
            ]
        )
        catalog = await projection._read_espo_catalog(client)
        assert len(catalog["ssp2-4.5"]) == 1

    async def test_retries_parse_error(self, no_sleep):
        xml = catalog_xml([("CanESM5", "ssp245"), ("CanESM5", "ssp370")])
        client = make_client(
            [make_response(text="<html>proxy error</html>")] * 1
            + [make_response(text=xml)]
        )
        catalog = await projection._read_espo_catalog(client)
        assert len(catalog["ssp3-7.0"]) == 1

    async def test_exhausted_attempts_raise(self, no_sleep):
        client = make_client(
            [make_response(error=projection.httpx.HTTPError("down"))] * 3
        )
        with pytest.raises(RuntimeError, match="ESPO catalog"):
            await projection._read_espo_catalog(client)


class TestParseCatalog:
    def test_sorted_models_per_scenario(self):
        xml = catalog_xml(
            [
                ("MIROC6", "ssp245"),
                ("CanESM5", "ssp245"),
                ("CanESM5", "ssp370"),
            ]
        )
        catalog = projection._parse_catalog(xml)
        assert [model for model, _ in catalog["ssp2-4.5"]] == [
            "CanESM5",
            "MIROC6",
        ]
        assert catalog["ssp2-4.5"][0][1].startswith(
            projection.espo_opendap_base
        )

    def test_ssp585_is_ignored(self):
        xml = catalog_xml(
            [
                ("CanESM5", "ssp245"),
                ("CanESM5", "ssp370"),
                ("CanESM5", "ssp585"),
            ]
        )
        catalog = projection._parse_catalog(xml)
        assert set(catalog) == {"ssp2-4.5", "ssp3-7.0"}

    def test_360_day_span_is_not_matched(self):
        # UKESM1-0-LL files end 21001230 (360-day calendar) and must not
        # become tasks
        xml = catalog_xml([("CanESM5", "ssp245"), ("CanESM5", "ssp370")])
        xml += (
            '\n<dataset urlPath="day_ESPO-G6-R2_v1.0.0_CMIP6_ScenarioMIP_'
            'NAM_MOHC_UKESM1-0-LL_ssp245_r1i1p1f2_19500101-21001230.ncml"/>'
        )
        catalog = projection._parse_catalog(xml)
        assert [model for model, _ in catalog["ssp2-4.5"]] == ["CanESM5"]

    def test_duplicate_model_raises(self):
        xml = catalog_xml([("CanESM5", "ssp245"), ("CanESM5", "ssp245")])
        with pytest.raises(ValueError, match="Duplicate model"):
            projection._parse_catalog(xml)

    def test_scenario_without_models_raises(self):
        xml = catalog_xml([("CanESM5", "ssp245")])
        with pytest.raises(ValueError, match="no models for ssp3-7.0"):
            projection._parse_catalog(xml)


class TestStationWeights:
    def test_weights_cover_every_station(self, stations_df):
        grid = make_grid()
        box, weights = projection._station_weights(stations_df, grid)
        (j0, j1), (i0, i1) = box
        assert 0 <= j0 <= j1 < grid.rlat.size
        assert 0 <= i0 <= i1 < grid.rlon.size
        assert set(weights) == set(stations_df["id"])
        n_cells = (j1 - j0 + 1) * (i1 - i0 + 1)
        for cells, coverage in weights.values():
            assert cells.size > 0
            assert (cells < n_cells).all()
            assert (coverage > 0).all()

    def test_uses_download_geometry_helpers(self, monkeypatch, stations_df):
        # the helpers must resolve through `holmes.download.geometry`, not
        # through copies or the legacy `holmes.data.weather` privates
        grid = make_grid()
        calls = []
        real_to_geopandas = geometry.to_geopandas
        real_coverage = geometry.compute_coverage_weights

        def spy_to_geopandas(stations):
            calls.append("to_geopandas")
            return real_to_geopandas(stations)

        def spy_coverage(polygons, template):
            calls.append("compute_coverage_weights")
            return real_coverage(polygons, template)

        monkeypatch.setattr(geometry, "to_geopandas", spy_to_geopandas)
        monkeypatch.setattr(geometry, "compute_coverage_weights", spy_coverage)
        projection._station_weights(stations_df, grid)
        assert calls == ["to_geopandas", "compute_coverage_weights"]


class TestReadMember:
    @pytest.fixture
    def weights(self):
        return {"061004": (np.array([0, 1]), np.array([0.5, 0.5]))}

    async def test_cached_member_resumes_without_fetching(
        self, tmp_data_dir, monkeypatch, weights
    ):
        task = projection._MemberTask(
            "ESPO-G6-R2", "ssp2-4.5", "CanESM5", "https://espo", None, ("pr",)
        )
        path = projection._member_path("061004", "ssp2-4.5", "CanESM5")
        path.parent.mkdir(exist_ok=True, parents=True)
        pl.DataFrame({"id": ["061004"]}).write_ipc(path)
        fetch = AsyncMock(side_effect=AssertionError("must not fetch"))
        monkeypatch.setattr(projection, "_fetch_window", fetch)
        await projection._read_member(
            asyncio.Semaphore(1),
            MagicMock(),
            task,
            make_grid(),
            ((0, 1), (0, 1)),
            weights,
            rebuild=False,
        )

    async def test_espo_member_derives_temperature(
        self, tmp_data_dir, monkeypatch, weights
    ):
        grid = make_grid()
        task = projection._MemberTask(
            "ESPO-G6-R2",
            "ssp2-4.5",
            "CanESM5",
            "https://espo",
            None,
            ("pr", "tasmin", "tasmax"),
        )
        check = AsyncMock()
        monkeypatch.setattr(projection, "_check_dds", check)
        values = {
            "pr": np.full((3, 2, 3), 1e-5, dtype=np.float32),
            "tasmin": np.full((3, 2, 3), 263.15, dtype=np.float32),
            "tasmax": np.full((3, 2, 3), 283.15, dtype=np.float32),
        }

        async def fetch(semaphore, client, task_, var, start, end, box):
            return values[var]

        monkeypatch.setattr(projection, "_fetch_window", fetch)
        # the mean must resolve through `holmes.download.geometry`
        means = []
        real_mean = geometry.calculate_masked_mean

        def spy_mean(values_, cells, coverage):
            means.append(True)
            return real_mean(values_, cells, coverage)

        monkeypatch.setattr(geometry, "calculate_masked_mean", spy_mean)
        await projection._read_member(
            asyncio.Semaphore(1),
            MagicMock(),
            task,
            grid,
            ((0, 1), (0, 2)),
            weights,
            rebuild=False,
        )
        check.assert_awaited_once()
        assert means
        data = pl.read_ipc(
            projection._member_path("061004", "ssp2-4.5", "CanESM5"),
            memory_map=False,
        )
        assert data["precipitation"].to_list() == pytest.approx(
            [1e-5 * 86400] * 3, abs=1e-4
        )
        # (tasmin + tasmax) / 2 - 273.15, within float32 precision
        assert data["temperature"].to_list() == pytest.approx(
            [0.0] * 3, abs=1e-4
        )
        assert data["scenario"].unique().to_list() == ["ssp2-4.5"]

    async def test_climex_member_uses_tas(
        self, tmp_data_dir, monkeypatch, weights
    ):
        grid = make_grid()
        task = projection._MemberTask(
            "ClimEx", "rcp8.5", "r1", "https://climex", 3, ("pr", "tas")
        )
        check = AsyncMock(side_effect=AssertionError("no dds for climex"))
        monkeypatch.setattr(projection, "_check_dds", check)
        values = {
            "pr": np.zeros((3, 2, 3), dtype=np.float32),
            "tas": np.full((3, 2, 3), 274.15, dtype=np.float32),
        }

        async def fetch(semaphore, client, task_, var, start, end, box):
            return values[var]

        monkeypatch.setattr(projection, "_fetch_window", fetch)
        await projection._read_member(
            asyncio.Semaphore(1),
            MagicMock(),
            task,
            grid,
            ((0, 1), (0, 2)),
            weights,
            rebuild=False,
        )
        data = pl.read_ipc(
            projection._member_path("061004", "rcp8.5", "r1"),
            memory_map=False,
        )
        assert data["temperature"].to_list() == pytest.approx(
            [1.0] * 3, abs=1e-4
        )


class TestCheckDds:
    @pytest.fixture
    def task(self) -> projection._MemberTask:
        return projection._MemberTask(
            "ESPO-G6-R2", "ssp2-4.5", "CanESM5", "https://espo", None, ("pr",)
        )

    @staticmethod
    def dds_text(grid: projection._GridMetadata) -> str:
        return (
            f"Dataset {{ Float32 pr[time = {grid.n_times}]"
            f"[rlat = {grid.rlat.size}][rlon = {grid.rlon.size}]; }} d;"
        )

    async def test_valid_axes_pass(self, task):
        grid = make_grid()
        client = make_client([make_response(text=self.dds_text(grid))])
        await projection._check_dds(asyncio.Semaphore(1), client, task, grid)

    async def test_retries_then_succeeds(self, no_sleep, task):
        grid = make_grid()
        client = make_client(
            [
                make_response(error=projection.httpx.HTTPError("boom")),
                make_response(text=self.dds_text(grid)),
            ]
        )
        await projection._check_dds(asyncio.Semaphore(1), client, task, grid)

    async def test_wrong_axes_exhaust_attempts(self, no_sleep, task):
        grid = make_grid()
        wrong = self.dds_text(grid).replace(
            f"time = {grid.n_times}", "time = 1"
        )
        client = make_client([make_response(text=wrong)] * 3)
        with pytest.raises(RuntimeError, match="Could not validate"):
            await projection._check_dds(
                asyncio.Semaphore(1), client, task, grid
            )


class TestValidateDds:
    def test_size_mismatch_names_the_axis(self):
        grid = make_grid()
        text = (
            f"Dataset {{ Float32 pr[time = {grid.n_times}]"
            f"[rlat = {grid.rlat.size}][rlon = 999]; }} d;"
        )
        with pytest.raises(ValueError, match="rlon"):
            projection._validate_dds(text, grid, "https://espo")


class TestFetchWindow:
    @pytest.fixture
    def box(self) -> tuple[tuple[int, int], tuple[int, int]]:
        return ((0, 1), (0, 2))

    async def test_espo_window(self, box):
        task = projection._MemberTask(
            "ESPO-G6-R2", "ssp2-4.5", "CanESM5", "https://espo", None, ("pr",)
        )
        values = np.arange(2 * 2 * 3, dtype=np.float32).reshape(2, 2, 3)
        client = make_client([make_response(content=make_dods(values))])
        window = await projection._fetch_window(
            asyncio.Semaphore(1), client, task, "pr", 0, 1, box
        )
        assert window.shape == (2, 2, 3)
        assert np.allclose(window, values)

    async def test_climex_window_drops_realization_axis(self, box):
        task = projection._MemberTask(
            "ClimEx", "rcp8.5", "r1", "https://climex", 3, ("pr",)
        )
        values = np.arange(1 * 2 * 2 * 3, dtype=np.float32).reshape(1, 2, 2, 3)
        client = make_client([make_response(content=make_dods(values))])
        window = await projection._fetch_window(
            asyncio.Semaphore(1), client, task, "pr", 0, 1, box
        )
        assert window.shape == (2, 2, 3)
        assert np.allclose(window, values[0])

    async def test_retries_then_succeeds(self, no_sleep, box):
        task = projection._MemberTask(
            "ESPO-G6-R2", "ssp2-4.5", "CanESM5", "https://espo", None, ("pr",)
        )
        values = np.zeros((2, 2, 3), dtype=np.float32)
        client = make_client(
            [
                make_response(error=projection.httpx.HTTPError("boom")),
                make_response(content=make_dods(values)),
            ]
        )
        window = await projection._fetch_window(
            asyncio.Semaphore(1), client, task, "pr", 0, 1, box
        )
        assert window.shape == (2, 2, 3)

    async def test_exhausted_attempts_raise(self, no_sleep, box):
        task = projection._MemberTask(
            "ESPO-G6-R2", "ssp2-4.5", "CanESM5", "https://espo", None, ("pr",)
        )
        client = make_client(
            [make_response(content=b"<html>error</html>")] * 3
        )
        with pytest.raises(RuntimeError, match="Could not fetch"):
            await projection._fetch_window(
                asyncio.Semaphore(1), client, task, "pr", 0, 1, box
            )


class TestConstraint:
    def test_espo_3d(self):
        task = projection._MemberTask(
            "ESPO-G6-R2", "ssp2-4.5", "CanESM5", "https://espo", None, ("pr",)
        )
        constraint, shape = projection._constraint(
            task, "pr", 10, 19, ((2, 4), (5, 9))
        )
        assert constraint == "pr.pr[10:1:19][2:1:4][5:1:9]"
        assert shape == (10, 3, 5)

    def test_climex_4d(self):
        task = projection._MemberTask(
            "ClimEx", "rcp8.5", "r1", "https://climex", 7, ("pr",)
        )
        constraint, shape = projection._constraint(
            task, "pr", 0, 1, ((0, 1), (0, 1))
        )
        assert constraint == "pr.pr[7:1:7][0:1:1][0:1:1][0:1:1]"
        assert shape == (1, 2, 2, 2)


class TestParseDods:
    def test_round_trip(self):
        values = np.arange(12, dtype=np.float32).reshape(2, 2, 3)
        parsed = projection._parse_dods(make_dods(values), (2, 2, 3))
        assert np.allclose(parsed, values)

    def test_missing_marker_raises(self):
        with pytest.raises(ValueError, match="Not a DAP2 response"):
            projection._parse_dods(b"<html>proxy error</html>", (1,))

    def test_shape_mismatch_raises(self):
        values = np.zeros((2, 2, 3), dtype=np.float32)
        with pytest.raises(ValueError, match="Expected shape"):
            projection._parse_dods(make_dods(values), (2, 2, 4))

    def test_truncated_body_raises(self):
        values = np.zeros((2, 2, 3), dtype=np.float32)
        body = make_dods(values)[:-8]
        with pytest.raises(ValueError, match="Truncated"):
            projection._parse_dods(body, (2, 2, 3))

    def test_wrong_counts_raise(self):
        values = np.zeros((2, 2, 3), dtype=np.float32)
        body = make_dods(values)
        index = body.find(b"\nData:\n") + len(b"\nData:\n")
        corrupted = body[:index] + struct.pack(">II", 5, 5) + body[index + 8 :]
        with pytest.raises(ValueError, match="counts"):
            projection._parse_dods(corrupted, (2, 2, 3))


class TestReadGridMetadata:
    @staticmethod
    def make_dataset(
        *,
        origin: str = "2019-01-01",
        periods: int = (2099 - 2019) * 365 + 365,
        realization: bool = False,
        rlon_shift: bool = False,
        attrs: dict | None = None,
    ) -> xr.Dataset:
        times = xr.date_range(
            start=origin, periods=periods, calendar="noleap", use_cftime=True
        )
        rlat = np.arange(47.35, 48.75, 0.1)
        rlon = np.arange(-71.85, -70.35, 0.1)
        if rlon_shift:
            rlon = rlon + 360.0
        coords = {"time": times, "rlat": rlat, "rlon": rlon}
        if realization:
            coords["realization"] = np.array(
                [b"historical-r1-r1i1p1", b"historical-r2-r2i1p1"]
            )
        data = xr.Dataset(coords=coords)
        data["rotated_pole"] = xr.DataArray(
            0, attrs=identity_pole if attrs is None else attrs
        )
        return data

    def patch_open(self, monkeypatch, dataset: xr.Dataset) -> None:
        opened = MagicMock()
        opened.__enter__ = MagicMock(return_value=dataset)
        opened.__exit__ = MagicMock(return_value=False)
        monkeypatch.setattr(
            projection.xr, "open_dataset", lambda url, **kwargs: opened
        )

    def test_nominal_with_members_and_shift(self, monkeypatch):
        self.patch_open(
            monkeypatch,
            self.make_dataset(realization=True, rlon_shift=True),
        )
        grid = projection._read_grid_metadata("https://climex")
        assert grid.members == [
            "historical-r1-r1i1p1",
            "historical-r2-r2i1p1",
        ]
        assert grid.rlon.max() < 180.0
        assert grid.datetimes[0] == datetime(2020, 1, 1)
        assert grid.datetimes[-1] == datetime(2099, 12, 30)
        assert grid.start == 365

    def test_missing_pole_attrs_raise(self, monkeypatch):
        self.patch_open(
            monkeypatch,
            self.make_dataset(attrs={"grid_mapping_name": "x"}),
        )
        with pytest.raises(ValueError, match="rotated pole"):
            projection._read_grid_metadata("https://climex")

    def test_axis_not_covering_span_raises(self, monkeypatch):
        self.patch_open(monkeypatch, self.make_dataset(origin="2050-01-01"))
        with pytest.raises(ValueError, match="Time axis does not cover"):
            projection._read_grid_metadata("https://climex")

    def test_shifted_landing_date_raises(self, monkeypatch):
        # a mid-year origin breaks the (year - origin) x 365 arithmetic
        self.patch_open(monkeypatch, self.make_dataset(origin="2019-06-01"))
        with pytest.raises(ValueError, match="Expected"):
            projection._read_grid_metadata("https://climex")


class TestBoundingBox:
    def test_margin_of_one_cell(self, stations_df):
        grid = make_grid()
        polygons = geometry.to_geopandas(stations_df).to_crs(grid.crs)
        (j0, j1), (i0, i1) = projection._bounding_box(polygons, grid)
        min_x, min_y, max_x, max_y = polygons.total_bounds
        assert grid.rlat[j0] < min_y
        assert grid.rlat[j1] > max_y
        assert grid.rlon[i0] < min_x
        assert grid.rlon[i1] > max_x

    def test_outside_domain_raises(self, stations_df):
        grid = make_grid()._replace(rlat=np.arange(10.0, 11.0, 0.1))
        polygons = geometry.to_geopandas(stations_df)
        with pytest.raises(ValueError, match="outside the projection"):
            projection._bounding_box(polygons, grid)


class TestWindows:
    def test_single_window(self):
        grid = make_grid(start=100, end=200)
        assert projection._windows(grid) == [(100, 200)]

    def test_multiple_windows_clamp_to_end(self, monkeypatch):
        monkeypatch.setattr(projection, "window_years", 1)
        grid = make_grid(start=0, end=800)
        assert projection._windows(grid) == [(0, 364), (365, 729), (730, 800)]


class TestPaths:
    def test_paths_live_under_data_dir(self, tmp_data_dir):
        assert projection._product_path("061004") == (
            tmp_data_dir / "raw" / "projection" / "061004.ipc"
        )
        assert projection._member_path("061004", "rcp8.5", "r1") == (
            tmp_data_dir
            / "raw"
            / "projection"
            / "061004"
            / "rcp8.5"
            / "r1.ipc"
        )
