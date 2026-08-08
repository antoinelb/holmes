import asyncio
import re
import struct
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

import geopandas as gpd
import geopolars as gpl
import httpx
import numpy as np
import numpy.typing as npt
import polars as pl
import pyproj
import rioxarray  # noqa: F401  # registers the .rio accessor
import xarray as xr

from holmes.utils.paths import data_dir
from holmes.utils.print import done_print, load_progress

from .weather import (
    _calculate_masked_mean,
    _compute_coverage_weights,
    download_release_asset,
)

#############
# constants #
#############

# the ClimEx CRCM5 50-member large ensemble (CanESM2-driven, RCP8.5),
# served by PAVICS as a single aggregated OPeNDAP dataset: daily values on
# a 0.11 deg rotated-pole grid, noleap calendar from 1955-01-01 to
# 2099-12-30 (the last year is one day short)
climex_url = (
    "https://pavics.ouranos.ca/twitcher/ows/proxy/thredds/dodsC/"
    "datasets/simulations/climex/day_climex-crcm5_historical+rcp85.ncml"
)

climex_scenario = "rcp8.5"

n_members = 50

# the ESPO-G6-R2 v1.0.0 bias-adjusted CMIP6 ensemble, one OPeNDAP dataset
# per (institution, model, scenario) on a 0.1 deg rotated-pole NAM grid,
# noleap calendar from 1950-01-01 to 2100-12-31; the model list is read
# from the catalog rather than hardcoded
espo_catalog_url = (
    "https://pavics.ouranos.ca/twitcher/ows/proxy/thredds/catalog/"
    "datasets/simulations/bias_adjusted/cmip6/ouranos/ESPO-G/"
    "ESPO-G6-R2v1.0.0/catalog.xml"
)
espo_opendap_base = (
    "https://pavics.ouranos.ca/twitcher/ows/proxy/thredds/dodsC/"
)

# dataset scenario tokens -> display labels; ssp585 is deliberately absent
espo_scenarios = {"ssp245": "ssp2-4.5", "ssp370": "ssp3-7.0"}

# both ensembles are clipped to the same window, from the start year to
# ClimEx's dataset end, so every scenario/member series spans the same days
projection_start_year = 2020
projection_end_date = (2099, 12, 30)

# raw DAP2 slices over httpx rather than xarray/netCDF4: netCDF4 keeps a
# global lock, so threaded reads barely overlap (~1.3x), while ten plain
# concurrent requests cut a cold download from ~100 to ~15 minutes. The
# THREDDS subset service is not an option either — its writer chokes on an
# int64 attribute of the ClimEx dataset — so requests go to the OPeNDAP
# endpoint.
fetch_concurrency = 10

# one request per member and variable, covering the whole span (~8-10 MB):
# the server's fixed per-request cost dominates — ClimEx re-opens its
# 50-file aggregation on every request (~6.5 s) while marginal data is
# ~1.6 MB/s — so fewer, bigger requests win, and a ~10 s retry stays cheap
window_years = 80

fetch_attempts = 3

##########
# public #
##########


def has_projection_data(stations: pl.DataFrame) -> bool:
    """Whether every given station already has its cached product."""
    return all(_product_path(id_).exists() for id_ in stations["id"])


async def read_projection_data(
    stations: pl.DataFrame, *, rebuild: bool = False
) -> pl.DataFrame:
    """Daily projected forcing averaged over each station's watershed.

    `stations` is the station frame filtered to the wanted ids. Returns one
    row per station, ensemble ("ClimEx" or "ESPO-G6-R2"), scenario
    ("rcp8.5" for ClimEx, "ssp2-4.5" and "ssp3-7.0" for ESPO), member (the
    ClimEx realization label, e.g.
    "historical-r1-r1i1p1", or the ESPO driving model, e.g. "CanESM5") and
    day from 2020-01-01 to 2099-12-30, with precipitation in mm/day and
    temperature in deg C. The noleap calendar means no Feb 29 rows, which
    is fine downstream: the models only use the day of year.
    """
    if stations.height == 0:
        raise ValueError("No stations to read projection data for.")

    ids = stations["id"].to_list()
    if rebuild:
        missing = ids
    else:
        # the products are published as release assets (`make
        # upload-assets`): a fresh install downloads them rather than
        # rebuilding from PAVICS; a failure falls through to the build
        for id_ in ids:
            if not _product_path(id_).exists():
                download_release_asset(f"{id_}.ipc", _product_path(id_))
        missing = [id_ for id_ in ids if not _product_path(id_).exists()]
    if missing:
        await _build_products(
            stations.filter(pl.col("id").is_in(missing)), rebuild=rebuild
        )

    return pl.concat(
        # memory mapping is unavailable on the compressed cache and warns
        # loudly about it; the read costs ~20 ms either way
        [pl.read_ipc(_product_path(id_), memory_map=False) for id_ in ids]
    ).sort("id", "ensemble", "scenario", "member", "datetime")


###########
# private #
###########


async def _build_products(stations: pl.DataFrame, *, rebuild: bool) -> None:
    semaphore = asyncio.Semaphore(fetch_concurrency)
    async with httpx.AsyncClient(timeout=300.0) as client:
        catalog = await _read_espo_catalog(client)
        # every ESPO dataset shares the NAM grid, so any serves as the
        # metadata representative; each dataset's own axes are still
        # checked against it before being fetched
        espo_url = next(iter(catalog.values()))[0][1]
        climex_grid, espo_grid = await asyncio.gather(
            asyncio.to_thread(_read_grid_metadata, climex_url),
            asyncio.to_thread(_read_grid_metadata, espo_url),
        )
        if len(climex_grid.members) != n_members:
            raise ValueError(
                f"Expected {n_members} ClimEx members, "
                f"found {len(climex_grid.members)}."
            )

        climex_box, climex_weights = _station_weights(stations, climex_grid)
        espo_box, espo_weights = _station_weights(stations, espo_grid)

        specs = [
            (
                _MemberTask(
                    "ClimEx",
                    climex_scenario,
                    member,
                    climex_url,
                    index,
                    ("pr", "tas"),
                ),
                climex_grid,
                climex_box,
                climex_weights,
            )
            for index, member in enumerate(climex_grid.members)
        ] + [
            (
                _MemberTask(
                    "ESPO-G6-R2",
                    scenario,
                    model,
                    url,
                    None,
                    ("pr", "tasmin", "tasmax"),
                ),
                espo_grid,
                espo_box,
                espo_weights,
            )
            for scenario, models in catalog.items()
            for model, url in models
        ]

        tasks = [
            asyncio.create_task(
                _read_member(
                    semaphore,
                    client,
                    member,
                    grid,
                    box,
                    weights,
                    rebuild=rebuild,
                )
            )
            for member, grid, box, weights in specs
        ]
        try:
            for task in load_progress(
                asyncio.as_completed(tasks),
                "Reading projection data...",
                total=len(tasks),
            ):
                await task
        except BaseException:
            # a failed member aborts the whole read (partial data would
            # surface as silent gaps the models reject); reap the rest so
            # nothing keeps hitting the server
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

    for id_ in stations["id"]:
        data = pl.concat(
            [
                pl.read_ipc(
                    _member_path(id_, member.scenario, member.member),
                    memory_map=False,
                )
                # the ensemble is task metadata, stamped at assembly so the
                # per-member caches predating the column stay valid
                .with_columns(pl.lit(member.ensemble).alias("ensemble"))
                for member, *_ in specs
            ]
        ).select(
            "id",
            "ensemble",
            "scenario",
            "member",
            "datetime",
            "precipitation",
            "temperature",
        )
        data.write_ipc(_product_path(id_), compression="zstd")
    done_print("Read projection data.")


async def _read_espo_catalog(
    client: httpx.AsyncClient,
) -> dict[str, list[tuple[str, str]]]:
    """Models and dataset URLs per wanted scenario, read from the catalog.

    Reading the catalog rather than hardcoding the model list keeps the
    tasks aligned with what PAVICS actually serves; the version-pinned
    path keeps the answer stable.
    """
    last_error: Exception | None = None
    for attempt in range(fetch_attempts):
        if attempt:
            await asyncio.sleep(2**attempt)
        try:
            response = await client.get(espo_catalog_url)
            response.raise_for_status()
            # parse errors retry too: a proxy error page can come back 200
            return _parse_catalog(response.text)
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(
        f"Could not read the ESPO catalog after {fetch_attempts} attempts "
        f"({last_error})."
    )


def _parse_catalog(xml: str) -> dict[str, list[tuple[str, str]]]:
    """(model, dataset URL) pairs per scenario label, sorted by model.

    The regex anchors the advertised 1950-2100 span, so a dataset with a
    different time axis never becomes a task — deliberately dropping
    UKESM1-0-LL and KACE-1-0-G, which ESPO leaves on their native 360-day
    calendar (their files end 21001230): the x365 noleap index math cannot
    serve them. CMIP6 institution and model ids never contain underscores,
    so the fields split unambiguously (the variant part absorbs CNRM's
    r1i1p1f2).
    """
    pattern = re.compile(
        r'urlPath="([^"]*_NAM_[A-Za-z0-9-]+_([A-Za-z0-9-]+)_(ssp\d+)'
        r'_r\d+i\d+p\d+f\d+_19500101-21001231\.ncml)"'
    )
    catalog: dict[str, list[tuple[str, str]]] = {
        label: [] for label in espo_scenarios.values()
    }
    for path, model, token in pattern.findall(xml):
        label = espo_scenarios.get(token)
        if label is None:
            continue
        if any(model == existing for existing, _ in catalog[label]):
            raise ValueError(f"Duplicate model {model} for {label}.")
        catalog[label].append((model, f"{espo_opendap_base}{path}"))
    for label, models in catalog.items():
        if not models:
            raise ValueError(f"The catalog lists no models for {label}.")
        models.sort()
    return catalog


def _station_weights(
    stations: pl.DataFrame, grid: "_GridMetadata"
) -> tuple[
    tuple[tuple[int, int], tuple[int, int]],
    dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]],
]:
    """Bounding box and coverage weights of the watersheds on one grid.

    Run once per ensemble: the two rotated poles differ, so the polygons
    must be reprojected for each grid.
    """
    polygons = (
        gpl.GeoDataFrame(stations.select("id", "geometry"))
        .to_geopandas()
        .set_crs("EPSG:4326")
        .to_crs(grid.crs)
    )
    box = _bounding_box(polygons, grid)
    return box, _compute_box_weights(polygons, grid, box)


class _MemberTask(NamedTuple):
    ensemble: str  # "ClimEx" or "ESPO-G6-R2"
    scenario: str  # display label ("rcp8.5", "ssp2-4.5", "ssp3-7.0")
    member: str  # realization label (ClimEx) or driving model (ESPO)
    url: str  # OPeNDAP dataset URL
    realization: int | None  # realization-axis position; None if 3D (ESPO)
    variables: tuple[str, ...]  # ("pr", "tas") or ("pr", "tasmin", "tasmax")


async def _read_member(
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
    task: _MemberTask,
    grid: "_GridMetadata",
    box: tuple[tuple[int, int], tuple[int, int]],
    weights: dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]],
    *,
    rebuild: bool,
) -> None:
    """Fetch one scenario member, reduce it per watershed and cache it.

    The per-member cache is the resume granularity: an interrupted cold
    download only refetches the members it had not finished.
    """
    if not rebuild and all(
        _member_path(id_, task.scenario, task.member).exists()
        for id_ in weights
    ):
        return

    if task.realization is None:
        # one dataset per member: guard each one's axes against the grid
        # the weights were computed on
        await _check_dds(semaphore, client, task, grid)

    arrays: dict[str, npt.NDArray[np.float64]] = {}
    for var in task.variables:
        windows = await asyncio.gather(
            *(
                _fetch_window(semaphore, client, task, var, start, end, box)
                for start, end in _windows(grid)
            )
        )
        stacked = np.concatenate(windows, axis=0)
        arrays[var] = stacked.astype(np.float64).reshape(len(stacked), -1)

    precipitation = arrays["pr"] * 86400.0  # kg m-2 s-1 -> mm/day
    if "tas" in arrays:
        temperature = arrays["tas"] - 273.15  # K -> deg C
    else:
        # ESPO publishes no daily mean; the min/max mean is its stand-in
        temperature = (arrays["tasmin"] + arrays["tasmax"]) / 2 - 273.15

    datetimes = pl.Series("datetime", grid.datetimes)
    for id_, (cells, coverage) in weights.items():
        data = pl.DataFrame(
            {
                "datetime": datetimes,
                "precipitation": _calculate_masked_mean(
                    precipitation, cells, coverage
                ),
                "temperature": _calculate_masked_mean(
                    temperature, cells, coverage
                ),
            }
        ).select(
            pl.lit(id_).alias("id"),
            pl.lit(task.scenario).alias("scenario"),
            pl.lit(task.member).alias("member"),
            "datetime",
            "precipitation",
            "temperature",
        )
        path = _member_path(id_, task.scenario, task.member)
        path.parent.mkdir(exist_ok=True, parents=True)
        data.write_ipc(path, compression="zstd")


async def _check_dds(
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
    task: _MemberTask,
    grid: "_GridMetadata",
) -> None:
    """Check a per-member dataset's declared axes against the shared grid.

    Grid metadata is read from one representative dataset; a sibling
    republished on other axes would silently mis-place every value. A tiny
    `.dds` text request per dataset is enough of a guard: with the noleap
    length pinned and the catalog regex anchoring the advertised
    1950-2100 span, a different origin cannot hide behind matching sizes.
    """
    last_error: Exception | None = None
    for attempt in range(fetch_attempts):
        if attempt:
            await asyncio.sleep(2**attempt)
        try:
            async with semaphore:
                response = await client.get(f"{task.url}.dds")
                response.raise_for_status()
            # parse errors retry too: a proxy error page can come back 200
            _validate_dds(response.text, grid, task.url)
            return
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(
        f"Could not validate the axes of {task.member} ({task.scenario}) "
        f"after {fetch_attempts} attempts ({last_error})."
    )


def _validate_dds(text: str, grid: "_GridMetadata", url: str) -> None:
    sizes = {
        name: int(size)
        for name, size in re.findall(r"\[(\w+) = (\d+)\]", text)
    }
    expected = {
        "time": grid.n_times,
        "rlat": grid.rlat.size,
        "rlon": grid.rlon.size,
    }
    for name, size in expected.items():
        if sizes.get(name) != size:
            raise ValueError(
                f"Expected {name} = {size} in {url}, found {sizes.get(name)}."
            )


async def _fetch_window(
    semaphore: asyncio.Semaphore,
    client: httpx.AsyncClient,
    task: _MemberTask,
    var: str,
    start: int,
    end: int,
    box: tuple[tuple[int, int], tuple[int, int]],
) -> npt.NDArray[np.float32]:
    constraint, shape = _constraint(task, var, start, end, box)

    last_error: Exception | None = None
    for attempt in range(fetch_attempts):
        if attempt:
            await asyncio.sleep(2**attempt)
        try:
            async with semaphore:
                response = await client.get(f"{task.url}.dods?{constraint}")
                response.raise_for_status()
            # parse errors retry too: a proxy error page can come back 200
            parsed = _parse_dods(response.content, shape)
            # normalize to (days, rlat, rlon): the realization axis, when
            # present, is sliced to length 1 and dropped here so callers
            # never index it — indexing a 3D reply would slice off days
            return parsed[0] if task.realization is not None else parsed
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(
        f"Could not fetch {var} for {task.member} ({task.scenario}) days "
        f"{start}-{end} after {fetch_attempts} attempts ({last_error})."
    )


def _constraint(
    task: _MemberTask,
    var: str,
    start: int,
    end: int,
    box: tuple[tuple[int, int], tuple[int, int]],
) -> tuple[str, tuple[int, ...]]:
    """DAP2 constraint and expected reply shape for one window."""
    (j0, j1), (i0, i1) = box
    space = f"[{start}:1:{end}][{j0}:1:{j1}][{i0}:1:{i1}]"
    shape = (end - start + 1, j1 - j0 + 1, i1 - i0 + 1)
    if task.realization is None:
        return f"{var}.{var}{space}", shape
    return (
        f"{var}.{var}[{task.realization}:1:{task.realization}]{space}",
        (1, *shape),
    )


def _parse_dods(
    body: bytes, shape: tuple[int, ...]
) -> npt.NDArray[np.float32]:
    """Array from a DAP2 binary response, validated against `shape`.

    The response is the DDS text, a `Data:` marker, then the element count
    as two big-endian uint32s followed by the raw big-endian float32
    values. The declared shape is checked so a server that reinterprets
    the constraint cannot silently return the wrong slice.
    """
    marker = b"\nData:\n"
    index = body.find(marker)
    if index == -1:
        raise ValueError(f"Not a DAP2 response: {body[:200]!r}")

    header = body[:index].decode("ascii", errors="replace")
    declared = tuple(
        int(size) for size in re.findall(r"\[\w+ = (\d+)\]", header)
    )
    if declared != shape:
        raise ValueError(f"Expected shape {shape}, server sent {declared}.")

    n = int(np.prod(shape))
    data = body[index + len(marker) :]
    if len(data) < 8 + 4 * n:
        raise ValueError("Truncated DAP2 response.")
    counts = struct.unpack_from(">II", data)
    if counts != (n, n):
        raise ValueError(f"Expected {n} values, got counts {counts}.")

    return np.frombuffer(data, dtype=">f4", count=n, offset=8).reshape(shape)


class _GridMetadata(NamedTuple):
    start: int  # time index of projection_start_year-01-01
    end: int  # time index of projection_end_date
    n_times: int  # full time-axis length, for sibling dataset checks
    datetimes: list[datetime]  # real dates for indices start..end
    members: list[str]  # realization labels; empty when the axis is absent
    rlat: npt.NDArray[np.float64]
    rlon: npt.NDArray[np.float64]
    crs: pyproj.CRS


def _read_grid_metadata(url: str) -> _GridMetadata:
    """Axes and projection of a dataset, read once per ensemble.

    The rotated-pole CRS is rebuilt from the dataset's own CF attributes
    (pyproj reproduces its 2D lat/lon to ~1e-5 deg), so the weights cannot
    drift from the grid if the dataset is republished.
    """
    with xr.open_dataset(url, decode_timedelta=False) as data:
        # the noleap calendar decodes to cftime objects, not datetime64
        times = data["time"].values.tolist()
        members = (
            [
                m.decode() if isinstance(m, bytes) else str(m)
                for m in data["realization"].values.tolist()
            ]
            if "realization" in data
            else []
        )
        # ESPO's float32 coordinates upcast with ~1e-6 deg rounding,
        # negligible against 0.1 deg cells
        rlat = np.asarray(data["rlat"].values, dtype=np.float64)
        rlon = np.asarray(data["rlon"].values, dtype=np.float64)
        attrs = dict(data["rotated_pole"].attrs)

    # ESPO publishes rlon in a 0-360-style range (324..388) while pyproj's
    # rotated CRS works in [-180, 180]; the uniform shift keeps the
    # lattice regular and only relabels the axis (fetches are by index)
    if rlon.min() > 180.0:
        rlon = rlon - 360.0

    keys = (
        "grid_mapping_name",
        "grid_north_pole_latitude",
        "grid_north_pole_longitude",
        "north_pole_grid_longitude",
    )
    if any(key not in attrs for key in keys[:3]):
        raise ValueError(
            f"Dataset lost its rotated pole mapping; has {sorted(attrs)}."
        )
    crs = pyproj.CRS.from_cf({key: attrs[key] for key in keys if key in attrs})

    # the noleap calendar makes the index math exact, but a republished
    # dataset with another origin, calendar or span would silently shift
    # every day, so both landing dates are checked
    origin = times[0].year
    start = (projection_start_year - origin) * 365
    end = (projection_end_date[0] - origin) * 365 + 363  # Dec 30, noleap
    if not 0 < start <= end < len(times):
        raise ValueError(
            f"Time axis does not cover {projection_start_year}-"
            f"{projection_end_date[0]}."
        )
    for index, expected in (
        (start, (projection_start_year, 1, 1)),
        (end, projection_end_date),
    ):
        found = times[index]
        if (found.year, found.month, found.day) != expected:
            raise ValueError(
                f"Expected {expected} at index {index}, found {found}."
            )

    return _GridMetadata(
        start=start,
        end=end,
        n_times=len(times),
        datetimes=[
            datetime(t.year, t.month, t.day) for t in times[start : end + 1]
        ],
        members=members,
        rlat=rlat,
        rlon=rlon,
        crs=crs,
    )


def _bounding_box(
    polygons: gpd.GeoDataFrame, grid: _GridMetadata
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Inclusive (rlat, rlon) index ranges covering every watershed.

    One cell of margin on each side so the edge cells' footprints are
    fully inside the fetched box.
    """
    min_x, min_y, max_x, max_y = polygons.total_bounds
    step_y = grid.rlat[1] - grid.rlat[0]
    step_x = grid.rlon[1] - grid.rlon[0]
    inside_y = np.flatnonzero(
        (grid.rlat >= min_y - step_y) & (grid.rlat <= max_y + step_y)
    )
    inside_x = np.flatnonzero(
        (grid.rlon >= min_x - step_x) & (grid.rlon <= max_x + step_x)
    )
    if inside_y.size == 0 or inside_x.size == 0:
        raise ValueError("The watersheds fall outside the projection domain.")
    return (
        (int(inside_y[0]), int(inside_y[-1])),
        (int(inside_x[0]), int(inside_x[-1])),
    )


def _compute_box_weights(
    polygons: gpd.GeoDataFrame,
    grid: _GridMetadata,
    box: tuple[tuple[int, int], tuple[int, int]],
) -> dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]]:
    """Coverage weights of each box cell for each watershed.

    Computed in the rotated CRS, where the lattice is regular: exactextract
    sees the same cells the fetches slice, so the map between `cell_id` and
    the flattened (rlat, rlon) arrays is exact. Coverage fractions stand in
    for areas because the cells are equal-sized in rotated coordinates
    (cos(rlat) varies by well under 1% across a watershed on both grids;
    ClimEx sits near the rotated equator, ESPO's pole differs but the
    domain stays far from it).
    """
    (j0, j1), (i0, i1) = box
    rlat = grid.rlat[j0 : j1 + 1]
    rlon = grid.rlon[i0 : i1 + 1]
    template = xr.Dataset(
        {
            "precipitation": (
                ("time", "y", "x"),
                np.zeros((1, rlat.size, rlon.size)),
            )
        },
        coords={"time": [0], "y": rlat, "x": rlon},
    )
    template = template.rio.set_spatial_dims(x_dim="x", y_dim="y")
    template = template.rio.write_crs(grid.crs)
    return _compute_coverage_weights(polygons, template)


def _windows(grid: _GridMetadata) -> list[tuple[int, int]]:
    step = window_years * 365
    return [
        (start, min(start + step - 1, grid.end))
        for start in range(grid.start, grid.end + 1, step)
    ]


def _product_path(id_: str) -> Path:
    return data_dir / "raw" / "projection" / f"{id_}.ipc"


def _member_path(id_: str, scenario: str, member: str) -> Path:
    return data_dir / "raw" / "projection" / id_ / scenario / f"{member}.ipc"
