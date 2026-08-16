"""Weather builders for the build layer behind `holmes download`.

Incremental counterparts to the read-side logic in `holmes.data.weather`
(which stays untouched until the final cleanup pass): each `update_*`
builder rebuilds its product from the true source when it is absent or
forced, and otherwise upserts only the refresh years, so a daily run
costs one small request per source. The `rebuild_*` builders are cheap
local transforms recomputed in full every run.
"""

import concurrent.futures
import tempfile
import zipfile
from datetime import date, datetime
from pathlib import Path

import cdsapi
import geopandas as gpd
import httpx
import numpy as np
import numpy.typing as npt
import polars as pl
import shapely
import xarray as xr

from holmes.data.archive import MissingDataError
from holmes.download import geometry

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths
from holmes.utils.print import progress_task, task, warn_print

#############
# constants #
#############

# every areal reduction happens in the same projected crs: degrees would
# over-weight the northern cells, since a 0.25 deg cell at 48N is far
# taller than it is wide
crs = "EPSG:32198"

# ERA5 is served on a regular 0.25 deg lat-lon grid; requests snap to it,
# so generating cell centres on the same lattice means one request per cell
era5_resolution = 0.25

# streamflow is on local calendar days, so the hourly UTC series is
# converted before the daily reduction rather than after
local_timezone = "America/Montreal"

# ERA5 begins in 1940, but station 061004 records from 1910; asking for
# the earlier years errors, so requests are clamped. CDS clips the recent
# end on its own, following the few-day reanalysis lag.
era5_start_year = 1940

# The MELCC daily station files were hand-delivered for the TP and have no
# public source; ids, names and coordinates come from the RSCQ open-data
# station list and the 1991-2020 climate normals.
stations_files = {
    "7060225": ("weather/stations/7060225_pikauba.csv", "Pikauba"),
    "7061439": ("weather/stations/7061439_chicoutimi.csv", "Chicoutimi"),
    "7066573": ("weather/stations/7066573_aux_ecorces.csv", "Aux Écorces"),
    "7066611": (
        "weather/stations/7066611_riviere_cyriac.csv",
        "Rivière-Cyriac",
    ),
    "7066820": (
        "weather/stations/7066820_saint_ambroise.csv",
        "Saint-Ambroise",
    ),
}

# the per-station reference series completing the observed records: the
# ministry-grid cell over each station where the grids have the day, the
# station's era5 cell otherwise
stations_backfill_file = "weather/stations_backfill.ipc"

# the GCQ-V3 daily climate grids, published as one NetCDF per parameter
# and year
ministry_grid_base_url = (
    "https://stqc380donopppdtce01.blob.core.windows.net/donnees-ouvertes/"
    "Climat/Analyses/Grilles_climatiques/Quotidien/NetCDF/"
)

# the grids start in 1940, like era5; earlier years simply do not exist
ministry_grid_start_year = 1940

# nearest-station picks are bounded by the UI slider
min_n_stations = 1
max_n_stations = 5

##########
# public #
##########


def update_era5(stations: pl.DataFrame, *, force: bool = False) -> None:
    """Build or refresh the era5.ipc product from Copernicus.

    Full build when the product is absent or `force`; otherwise only the
    refresh years are fetched per cell and upserted into the product.
    """
    with task(
        "Updating the ERA5 product...", "Updated the ERA5 product."
    ) as current:
        path = paths.data_dir / "raw" / "weather" / "era5.ipc"
        _unlink_legacy_era5_spans()

        grid = _era5_grid(geometry.to_geopandas(stations))
        cells = [
            (row["latitude"], row["longitude"])
            for row in grid.select("latitude", "longitude")
            .unique()
            .sort("latitude", "longitude")
            .to_dicts()
        ]

        if force or not path.exists():
            years = _station_years(stations, era5_start_year)
            fetched = _ensure_era5_cells(cells, years, refetch=False)
            data = _compute_era5_means(grid, _read_era5_years(cells, years))
            current.done_with(f"Rebuilt era5.ipc ({fetched} cell fetches).")
        else:
            years = _years_to_refresh(date.today())
            fetched = _ensure_era5_cells(cells, years, refetch=True)
            new = _compute_era5_means(grid, _read_era5_years(cells, years))
            data = _upsert_product(
                pl.read_ipc(path, memory_map=False),
                new,
                min(years),
                ("id", "datetime"),
            )
            current.done_with(
                f"Refreshed {', '.join(map(str, years))} in era5.ipc "
                f"({fetched} cell fetches)."
            )
        _write_ipc(path, data)


def update_ministry_grid(
    stations: pl.DataFrame, *, force: bool = False
) -> None:
    """Build or refresh the ministry_grid.ipc product from the GCQ-V3 grids.

    Full build when the product is absent or `force`; otherwise each
    refresh year's NetCDFs are redownloaded (the current year's file
    changes at the source) and the year is upserted. A refresh year that
    cannot be fetched keeps its old rows rather than opening a hole.
    """
    with task(
        "Updating the ministry grid product...",
        "Updated the ministry grid product.",
    ) as current:
        path = paths.data_dir / "raw" / "weather" / "ministry_grid.ipc"
        polygons = geometry.to_geopandas(stations).to_crs(crs)
        era5 = _read_era5_product()

        if force or not path.exists():
            years = _station_years(stations, ministry_grid_start_year)
            data = _fill_multiday_gaps_from_era5(
                _build_ministry_grid(polygons, years), era5
            )
            current.done_with(
                f"Rebuilt ministry_grid.ipc over {len(years)} years."
            )
        else:
            refresh = _years_to_refresh(date.today())
            new, failed = _refresh_ministry_years(polygons, refresh)
            if new is None:
                current.done_with("Kept ministry_grid.ipc unchanged.")
                return
            product = pl.read_ipc(path, memory_map=False)
            cutoff_year = min(y for y in refresh if y not in failed)
            cutoff = datetime(cutoff_year, 1, 1)
            # the gap-fill reference is restricted to the upserted rows;
            # the pre-cutoff rows were already filled when first built
            new = _fill_multiday_gaps_from_era5(
                new, era5.filter(pl.col("datetime") >= cutoff)
            )
            # a failed year's old rows ride along with the fresh rows so
            # the cutoff upsert can never open a hole
            carried = (
                product.filter(
                    (pl.col("datetime") >= cutoff)
                    & pl.col("datetime").dt.year().is_in(failed)
                )
                if failed
                else product.clear()
            )
            data = _upsert_product(
                product,
                pl.concat([new.select(product.columns), carried]),
                cutoff_year,
                ("id", "datetime"),
            )
            current.done_with(
                "Refreshed "
                f"{', '.join(str(y) for y in refresh if y not in failed)} "
                "in ministry_grid.ipc."
            )
        _write_ipc(path, data)


def update_stations_backfill(*, force: bool = False) -> None:
    """Build or refresh the per-station backfill from the raster caches.

    For each MELCC station: the ministry grid sampled at the cell
    containing the station, with the station's era5 cell filling the days
    the grids miss. Full build when absent or `force`; otherwise only the
    refresh years are sampled and upserted.
    """
    with task(
        "Updating the stations backfill...", "Updated the stations backfill."
    ) as current:
        path = paths.data_dir / "raw" / stations_backfill_file
        inventory = _read_station_inventory()

        if force or not path.exists():
            years = list(
                range(ministry_grid_start_year, date.today().year + 1)
            )
            data = _coalesce_backfill(
                _sample_ministry_grid(inventory, years),
                _sample_era5_cells(inventory, years),
            )
            current.done_with(f"Rebuilt {stations_backfill_file}.")
        else:
            years = _years_to_refresh(date.today())
            new = _coalesce_backfill(
                _sample_ministry_grid(inventory, years),
                _sample_era5_cells(inventory, years),
            )
            data = _upsert_product(
                pl.read_ipc(path, memory_map=False),
                new,
                min(years),
                ("climate_id", "datetime"),
            )
            current.done_with(
                f"Refreshed {', '.join(map(str, years))} in "
                f"{stations_backfill_file}."
            )
        _write_ipc(path, data)


def rebuild_completed_stations() -> None:
    """Recompute every completed-station series from csv + backfill.

    Always a full recompute: the transform is a cheap local join, and the
    backfill it reads may have just been upserted.
    """
    with progress_task(
        "Rebuilding the completed stations...",
        "Rebuilt the completed stations.",
        total=len(stations_files),
    ) as current:
        backfill = _read_backfill_product()
        for climate_id in sorted(stations_files):
            completed = _complete_station_series(
                _read_climate_station(climate_id),
                backfill.filter(pl.col("climate_id") == climate_id),
                climate_id,
            )
            _write_ipc(
                paths.data_dir
                / "raw"
                / "weather"
                / "stations_completed"
                / f"{climate_id}.ipc",
                completed,
            )
            current.increment()
        current.done_with(f"Rebuilt {len(stations_files)} completed stations.")


def rebuild_nearest_stations(stations: pl.DataFrame) -> None:
    """Recompute the nearest-station products for every slider position.

    Always a full recompute over the completed-station products, which
    `rebuild_completed_stations` must have written first.
    """
    with progress_task(
        "Rebuilding the nearest-station products...",
        "Rebuilt the nearest-station products.",
        total=max_n_stations - min_n_stations + 1,
    ) as current:
        polygons = geometry.to_geopandas(stations).to_crs(crs)
        inventory = _read_station_inventory()
        for n_stations in range(min_n_stations, max_n_stations + 1):
            selection = _select_nearest_stations(
                polygons, inventory, n_stations
            )
            if selection.is_empty():
                data = _empty_frame()
            else:
                # a station shared by two watersheds is read once and
                # joined twice
                series = pl.concat(
                    [
                        _read_completed_station_product(climate_id)
                        for climate_id in sorted(
                            set(selection["climate_id"].to_list())
                        )
                    ]
                )
                # the completion leaves the series dense, but the edges can
                # still be incomplete (the backfill sources start and stop
                # on different days), and an unfillable edge run would
                # crash the model layer's `_fill_missing`
                data = _trim_null_edges(_combine_idw(selection, series))
            _write_ipc(
                paths.data_dir
                / "raw"
                / f"weather/nearest_stations_{n_stations}.ipc",
                data,
            )
            current.increment()


def rebuild_grids(stations: pl.DataFrame) -> None:
    """Recompute the map-overlay grid products for every weather method.

    The exact frames `read_weather_grid` computes today, written as
    products so the server needs no rasters. The ministry one reads any
    cached NetCDF, guaranteed present after `update_ministry_grid`.
    """
    with task(
        "Rebuilding the weather grids...", "Rebuilt the weather grids."
    ) as current:
        polygons = geometry.to_geopandas(stations)
        directory = paths.data_dir / "raw" / "weather"
        _write_ipc(directory / "grid_era5.ipc", _era5_grid(polygons))
        _write_ipc(
            directory / "grid_ministry_grid.ipc",
            _ministry_grid_grid(polygons),
        )
        _write_ipc(
            directory / "grid_nearest_stations.ipc",
            _nearest_stations_grid(polygons),
        )
        current.done_with("Rebuilt 3 weather grids.")


###########
# private #
###########

##########
# shared #
##########


def _years_to_refresh(today: date) -> list[int]:
    """The calendar years a daily refresh must rebuild.

    Always the current year; January also refreshes the previous year,
    because the UTC→Montreal shift means closing local Dec 31 needs
    January's first UTC hours.
    """
    if today.month == 1:
        return [today.year - 1, today.year]
    return [today.year]


def _station_years(stations: pl.DataFrame, start_year: int) -> list[int]:
    """The contiguous build span from the stations' record spans.

    Clamped to the dataset's origin; an open-ended record runs to the
    current year.
    """
    if stations.is_empty():
        raise ValueError("No stations to build a year span from.")
    max_year = date.today().year
    spans = stations.select("start", "end").to_dicts()
    first = min(row["start"] for row in spans)
    last = max(
        row["end"] if row["end"] is not None else max_year for row in spans
    )
    return list(range(max(first, start_year), last + 1))


def _upsert_product(
    product: pl.DataFrame,
    new: pl.DataFrame,
    cutoff_year: int,
    sort_keys: tuple[str, str],
) -> pl.DataFrame:
    """Replace every product row from Jan 1 of `cutoff_year` with `new`."""
    cutoff = datetime(cutoff_year, 1, 1)
    return (
        product.filter(pl.col("datetime") < cutoff)
        .vstack(new.select(product.columns).cast(product.schema))
        .sort(*sort_keys)
    )


def _write_ipc(path: Path, data: pl.DataFrame) -> None:
    """Stage then atomically replace, so a crash never leaves a torn file."""
    path.parent.mkdir(exist_ok=True, parents=True)
    staged = path.with_suffix(".part")
    data.write_ipc(staged, compression="zstd")
    staged.replace(path)


########
# era5 #
########


def _unlink_legacy_era5_spans() -> None:
    """Drop the span-keyed cell caches ({lat}_{lon}_{start}_{end}.ipc).

    The per-year files replace them; a stale span file would otherwise sit
    on disk forever without ever being read.
    """
    directory = paths.data_dir / "raw" / "weather" / "era5"
    if not directory.exists():
        return
    for file in sorted(directory.glob("*.ipc")):
        if len(file.stem.split("_")) == 4:
            file.unlink()


def _ensure_era5_cells(
    cells: list[tuple[float, float]], years: list[int], *, refetch: bool
) -> int:
    """Fetch the per-year cell files the given years are missing.

    `refetch` drops the years' files first — the refresh path, where the
    trailing year's data has grown at the source. Returns the number of
    cell fetches made (one range request each).
    """
    if refetch:
        for latitude, longitude in cells:
            for year in years:
                _era5_cell_year_path(latitude, longitude, year).unlink(
                    missing_ok=True
                )

    needed = [
        (latitude, longitude, missing)
        for latitude, longitude in cells
        if (
            missing := [
                year
                for year in years
                if not _era5_cell_year_path(latitude, longitude, year).exists()
            ]
        )
    ]
    if not needed:
        return 0

    # every missing cell would fail the same way deep inside the pool, so
    # the credentials are checked once, up front, with a message that says
    # what to do about it
    _check_era5_credentials()

    # requests are network-bound and independent, so every cell is
    # submitted at once; CDS queues what it will not run concurrently and
    # cdsapi polls until each job comes up
    with progress_task(
        "Fetching ERA5 cells...",
        f"Fetched {len(needed)} ERA5 cells.",
        total=len(needed),
    ) as current:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(needed)
        ) as pool:
            futures = [
                pool.submit(
                    _fetch_era5_cell_years, latitude, longitude, missing_years
                )
                for latitude, longitude, missing_years in needed
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
                current.increment()
    return len(needed)


def _fetch_era5_cell_years(
    latitude: float, longitude: float, years: list[int]
) -> None:
    """One CDS range request for a cell, split into per-year files.

    The local-time shift drags the request's first UTC hours into the
    previous local year, which is only a partial day, so a leading partial
    year is never written; the trailing year may be partial too (CDS clips
    the future end) but is the refresh target, so it is written.
    """
    start, end = min(years), max(years)
    daily = _reduce_era5_cell(
        _download_era5_cell_range(latitude, longitude, start, end),
        latitude,
        longitude,
    ).with_columns(pl.col("datetime").dt.year().alias("year"))

    for year in range(start, end + 1):
        data = daily.filter(pl.col("year") == year).drop("year")
        # CDS covers every past year of the span; an empty frame can only
        # be a future year the request could not reach, and caching it
        # would mask the miss
        if not data.is_empty():
            _write_ipc(_era5_cell_year_path(latitude, longitude, year), data)


def _download_era5_cell_range(
    latitude: float, longitude: float, start_year: int, end_year: int
) -> pl.DataFrame:
    """Hourly series at one grid point, extracted server-side by CDS.

    The timeseries dataset returns a small csv per point rather than a
    gridded field, so decades of hourly data cost a few MB per cell.
    """
    # quiet: CDS logs a request id and every queue status change per cell,
    # which drowns the download's own progress output
    client = cdsapi.Client(quiet=True)

    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / "cell.zip"
        client.retrieve(
            "reanalysis-era5-single-levels-timeseries",
            {
                "variable": ["2m_temperature", "total_precipitation"],
                # the extra two days close local Dec 31 of the last year;
                # CDS clips an end in the future on its own
                "date": [f"{start_year}-01-01/{end_year + 1}-01-02"],
                "location": {"latitude": latitude, "longitude": longitude},
                "data_format": "csv",
            },
            archive,
        )
        with zipfile.ZipFile(archive, "r") as file:
            file.extractall(directory)

        csvs = sorted(Path(directory).glob("*.csv"))
        if not csvs:
            raise ValueError(
                f"CDS returned no csv for cell {latitude}, {longitude}."
            )

        return pl.concat([pl.read_csv(csv) for csv in csvs])


def _reduce_era5_cell(
    data: pl.DataFrame, latitude: float, longitude: float
) -> pl.DataFrame:
    """Hourly UTC to daily local values.

    ERA5 stamps each hourly accumulation at the *end* of the hour it
    covers, so the 00:00 stamp belongs to the previous day; shifting back
    an hour before taking the date puts every value on the day it fell.
    Note this is the ERA5 convention — ERA5-Land instead accumulates from
    00 UTC, and summing that would inflate totals roughly twelvefold.
    """
    return (
        data.select(
            (
                pl.col("valid_time")
                .str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S")
                .dt.replace_time_zone("UTC")
                .dt.convert_time_zone(local_timezone)
                - pl.duration(hours=1)
            ).alias("datetime"),
            # m to mm, matching the mm/day streamflow units
            (pl.col("tp") * 1000).alias("precipitation"),
            (pl.col("t2m") - 273.15).alias("temperature"),
        )
        .group_by(pl.col("datetime").dt.date())
        .agg(
            pl.col("precipitation").sum(),
            pl.col("temperature").mean(),
        )
        .select(
            pl.col("datetime").cast(pl.Datetime("us")),
            pl.col("precipitation"),
            pl.col("temperature"),
            pl.lit(latitude).alias("latitude"),
            pl.lit(longitude).alias("longitude"),
        )
        .sort("datetime")
    )


def _read_era5_years(
    cells: list[tuple[float, float]], years: list[int]
) -> pl.DataFrame:
    """Concatenate the per-year cell files, failing loudly on a miss.

    The trailing year alone may be absent for every cell: in the first
    days of January the reanalysis lag means CDS has not reached the new
    year yet, and the daily refresh must not fail for a week. Any other
    miss means partial coverage, which would silently skew the watershed
    means, so it raises.
    """
    frames: list[pl.DataFrame] = []
    for year in sorted(years):
        files = [
            _era5_cell_year_path(latitude, longitude, year)
            for latitude, longitude in cells
        ]
        existing = [file for file in files if file.exists()]
        if not existing and year == max(years):
            warn_print(f"No ERA5 data for {year} yet; skipping it.")
            continue
        if len(existing) < len(files):
            missing = [file.name for file in files if not file.exists()]
            raise RuntimeError(
                f"Missing ERA5 cell files after fetch: {', '.join(missing)}."
            )
        frames.extend(pl.read_ipc(file, memory_map=False) for file in existing)
    if not frames:
        raise RuntimeError(
            f"No ERA5 data for any of {', '.join(map(str, years))}."
        )
    return pl.concat(frames)


def _compute_era5_means(
    grid: pl.DataFrame, series: pl.DataFrame
) -> pl.DataFrame:
    """Area-weighted watershed means over the cells covering each one."""
    return (
        grid.select("id", "latitude", "longitude", "weight")
        .join(series, on=["latitude", "longitude"], how="inner")
        .group_by("id", "datetime")
        .agg(
            (
                (pl.col("precipitation") * pl.col("weight")).sum()
                / pl.col("weight").sum()
            ).alias("precipitation"),
            (
                (pl.col("temperature") * pl.col("weight")).sum()
                / pl.col("weight").sum()
            ).alias("temperature"),
        )
        .sort("id", "datetime")
    )


def _check_era5_credentials() -> None:
    try:
        # quiet here too: the logger is shared class state, so a single
        # loud client leaves an INFO handler behind for every later one
        cdsapi.Client(quiet=True)
    except Exception as exc:
        raise RuntimeError(
            "Missing ERA5 cell data has to be fetched from Copernicus. "
            "That needs an account: register at "
            "https://cds.climate.copernicus.eu, accept the ERA5 licence, "
            "then put your personal access token in ~/.cdsapirc:\n"
            "  url: https://cds.climate.copernicus.eu/api\n"
            "  key: <your-token>\n"
            "or set the CDSAPI_URL and CDSAPI_KEY environment variables."
        ) from exc


def _era5_cell_year_path(latitude: float, longitude: float, year: int) -> Path:
    return (
        paths.data_dir
        / "raw"
        / "weather"
        / "era5"
        / f"{latitude:.2f}_{longitude:.2f}_{year}.ipc"
    )


def _era5_lattice(value: float) -> float:
    return round(round(value / era5_resolution) * era5_resolution, 2)


def _era5_grid(polygons: gpd.GeoDataFrame) -> pl.DataFrame:
    """Cells intersecting each watershed, weighted by intersected area.

    Areas are measured in the projected crs: a 0.25 deg cell at 48N is far
    taller than it is wide, so intersecting in degrees would over-weight
    the northern cells.
    """
    assert era5_resolution > 0, "grid resolution must be positive"

    rows: list[dict[str, object]] = []

    for i in range(len(polygons)):
        id_ = str(polygons.iloc[i]["id"])
        watershed = polygons.geometry.iloc[i]
        cells = _era5_cells_covering(watershed.bounds)

        # projecting one watershed at a time keeps the frames small; areas
        # come out in m2 rather than square degrees
        projected = gpd.GeoSeries(cells, crs="EPSG:4326").to_crs(crs)
        clipped = gpd.GeoSeries([watershed], crs="EPSG:4326").to_crs(crs)
        areas = projected.intersection(clipped.iloc[0]).area.to_numpy()

        if areas.sum() <= 0:
            raise ValueError(
                f"No ERA5 cell intersects watershed {id_}; "
                "check the watershed geometry and its crs."
            )

        for cell, area in zip(cells, areas):
            if area <= 0:
                continue
            centre = cell.centroid
            rows.append(
                {
                    "id": id_,
                    "latitude": round(centre.y, 2),
                    "longitude": round(centre.x, 2),
                    "weight": float(area),
                    "geometry": shapely.to_geojson(cell),
                }
            )

    return pl.DataFrame(rows, schema=_grid_schema()) if rows else _empty_grid()


def _era5_cells_covering(
    bounds: tuple[float, float, float, float],
) -> list[shapely.Polygon]:
    """Grid cell boxes spanning a lat-lon bounding box.

    Cells are centred on multiples of the resolution, matching where CDS
    snaps a requested location, so the centres double as request
    coordinates.
    """
    min_lon, min_lat, max_lon, max_lat = bounds
    half = era5_resolution / 2

    def centres(low: float, high: float) -> npt.NDArray[np.float64]:
        first = np.floor(low / era5_resolution) * era5_resolution
        last = np.ceil(high / era5_resolution) * era5_resolution
        return np.arange(first, last + era5_resolution / 2, era5_resolution)

    return [
        shapely.box(lon - half, lat - half, lon + half, lat + half)
        for lat in centres(min_lat, max_lat)
        for lon in centres(min_lon, max_lon)
    ]


#################
# ministry grid #
#################


def _read_era5_product() -> pl.DataFrame:
    path = paths.data_dir / "raw" / "weather" / "era5.ipc"
    if not path.exists():
        raise MissingDataError(
            f"Missing {path}; run update_era5 first — the ministry grids "
            "have whole-domain missing days that only era5 can backfill."
        )
    return pl.read_ipc(path, memory_map=False)


def _build_ministry_grid(
    polygons: gpd.GeoDataFrame, years: list[int]
) -> pl.DataFrame:
    """Per-watershed daily means over every buildable year.

    A year that cannot be fetched is skipped rather than fatal: the rest
    of the record still makes a usable series.
    """
    _download_ministry_grid_files(
        [
            f"{parameter}_{year}.nc"
            for year in years
            for parameter in ("PREC", "TMOY")
        ]
    )

    weights: (
        dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]] | None
    ) = None
    frames: list[pl.DataFrame] = []
    with progress_task(
        "Reducing the ministry grids...",
        f"Reduced {len(years)} ministry grid years.",
        total=len(years),
    ) as current:
        for year in years:
            weather = _read_year_ministry_grid_weather_data(year)
            current.increment()
            if weather is None:
                continue
            # the lattice never changes across years, so the coverage
            # weights are computed once and reused
            if weights is None:
                weights = geometry.compute_coverage_weights(polygons, weather)
            frames.append(_reduce_year(polygons["id"], weather, weights))

    if frames:
        return pl.concat(frames, how="diagonal").sort("id", "datetime")
    return _empty_frame()


def _refresh_ministry_years(
    polygons: gpd.GeoDataFrame, years: list[int]
) -> tuple[pl.DataFrame | None, list[int]]:
    """Redownload each refresh year's grids and reduce them to means.

    Returns the fresh rows (None when every year failed) and the years
    whose files could not be fetched — the caller keeps their old rows.
    """
    weights: (
        dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]] | None
    ) = None
    frames: list[pl.DataFrame] = []
    failed: list[int] = []
    for year in years:
        # the current year's file changes at the source as days accrue, so
        # the cached copy is dropped and downloaded fresh
        for parameter in ("PREC", "TMOY"):
            (
                paths.data_dir
                / "raw"
                / "weather"
                / "ministry_grid"
                / f"{parameter}_{year}.nc"
            ).unlink(missing_ok=True)
        weather = _read_year_ministry_grid_weather_data(year)
        if weather is None:
            warn_print(
                f"Could not refresh the {year} ministry grids; keeping the "
                "existing rows."
            )
            failed.append(year)
            continue
        if weights is None:
            weights = geometry.compute_coverage_weights(polygons, weather)
        frames.append(_reduce_year(polygons["id"], weather, weights))

    if not frames:
        return None, failed
    return pl.concat(frames, how="diagonal").sort("id", "datetime"), failed


def _fill_multiday_gaps_from_era5(
    data: pl.DataFrame, era5: pl.DataFrame
) -> pl.DataFrame:
    """Backfill multi-day gaps from the complete era5 series.

    The source grids have whole-domain missing days that era5 does not; a
    run of two or more adjacent nulls would later make model calibration
    raise (`_fill_missing` interpolates only isolated gaps), so multi-day
    runs are backfilled while single-day gaps are left for interpolation.
    """
    reference = era5.select(
        "id",
        pl.col("datetime").dt.date().alias("date"),
        pl.col("precipitation").alias("era5_precipitation"),
        pl.col("temperature").alias("era5_temperature"),
    )
    # era5 is stamped at 00:00 and the grids at 05:00, so the join is on
    # the calendar date rather than the raw datetime
    filled = data.with_columns(
        pl.col("datetime").dt.date().alias("date")
    ).join(reference, on=["id", "date"], how="left")

    for column in ("precipitation", "temperature"):
        filled = filled.with_columns(
            pl.when(_multiday_gap_mask(column))
            .then(pl.col(f"era5_{column}"))
            .otherwise(pl.col(column))
            .alias(column)
        )

    return filled.drop("date", "era5_precipitation", "era5_temperature")


def _multiday_gap_mask(column: str) -> pl.Expr:
    """True where a missing day is part of a run of two or more.

    A single missing day has present neighbours on both sides, so it is
    left for `_fill_missing` to interpolate; any longer run has at least
    one missing neighbour, which is what marks it for the era5 backfill.
    """
    is_missing = pl.col(column).fill_nan(None).is_null()
    return (
        is_missing
        & (
            is_missing.shift(1, fill_value=False)
            | is_missing.shift(-1, fill_value=False)
        )
    ).over("id", order_by="datetime")


def _read_year_ministry_grid_weather_data(year: int) -> xr.Dataset | None:
    # only the two parameters the models need; the dataset also publishes
    # TMIN and TMAX, which nothing here reads
    precipitation_path = _ministry_grid_file(f"PREC_{year}.nc")
    mean_temperature_path = _ministry_grid_file(f"TMOY_{year}.nc")

    if precipitation_path is None or mean_temperature_path is None:
        return None

    precipitation = xr.load_dataset(precipitation_path, decode_coords="all")
    mean_temperature = xr.load_dataset(
        mean_temperature_path, decode_coords="all"
    )

    data = xr.merge(
        [precipitation, mean_temperature], join="exact", compat="override"
    )
    data = data.rio.set_spatial_dims(x_dim="x", y_dim="y")
    data = data.rio.write_crs(crs)

    return data[["PREC", "TMOY"]].rename(
        {"PREC": "precipitation", "TMOY": "temperature"}
    )


def _download_ministry_grid_files(names: list[str]) -> None:
    """Fetch the missing grid files concurrently before they are read.

    The year loops then hit warm files. `_ministry_grid_file` stages each
    file individually, so concurrent downloads of distinct names are safe,
    and a file that cannot be fetched stays missing: its year is skipped
    by the caller.
    """
    missing = [
        name
        for name in names
        if not (
            paths.data_dir / "raw" / "weather" / "ministry_grid" / name
        ).exists()
    ]
    if not missing:
        return
    with progress_task(
        "Downloading the ministry grids...",
        f"Downloaded {len(missing)} ministry grids.",
        total=len(missing),
    ) as current:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(missing)
        ) as pool:
            for _ in pool.map(_ministry_grid_file, missing):
                current.increment()


def _ministry_grid_file(name: str) -> Path | None:
    """Path to one GCQ-V3 NetCDF, downloading it first if it is missing.

    Returns None when it is neither cached nor reachable, so a single bad
    year does not abort the whole build.
    """
    path = paths.data_dir / "raw" / "weather" / "ministry_grid" / name

    if path.exists():
        return path

    staged = path.with_suffix(".part")
    try:
        path.parent.mkdir(exist_ok=True, parents=True)
        # streamed to disk rather than buffered: every missing grid is
        # fetched at once, and a cold cache holding one whole NetCDF in
        # memory per thread would not fit
        with httpx.stream(
            "GET",
            ministry_grid_base_url + name,
            timeout=300.0,
            follow_redirects=True,
        ) as response:
            response.raise_for_status()
            with staged.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)

        # a truncated body, or an error page served in place of the file,
        # would otherwise be cached as if it were data and fail on every
        # later read
        xr.open_dataset(staged).close()
        staged.replace(path)

        return path

    except Exception as exc:
        # a failed attempt must not strand a stale .part next to the cache
        staged.unlink(missing_ok=True)
        warn_print(f"Could not download {name} ({exc}).")
        return None


def _reduce_year(
    ids: pl.Series,
    weather: xr.Dataset,
    weights: dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]],
) -> pl.DataFrame:
    n_time = weather.sizes["time"]
    n_cells = weather.sizes["y"] * weather.sizes["x"]

    precipitation = weather["precipitation"].values.reshape(n_time, n_cells)
    temperature = weather["temperature"].values.reshape(n_time, n_cells)
    datetime_ = pl.Series(
        "datetime", weather.time.to_numpy()
    ).dt.cast_time_unit("us")

    data: list[pl.DataFrame] = []

    for id_ in ids:
        cell_ids, coverage = weights[id_]
        data.append(
            pl.DataFrame(
                {
                    "datetime": datetime_,
                    "precipitation": geometry.calculate_masked_mean(
                        precipitation, cell_ids, coverage
                    ),
                    "temperature": geometry.calculate_masked_mean(
                        temperature, cell_ids, coverage
                    ),
                }
            ).with_columns(pl.lit(id_).alias("id"))
        )
    return pl.concat(data)


############
# stations #
############


def _read_station_inventory() -> pl.DataFrame:
    """The MELCC stations: identifier, name, location and record span.

    Built from the csvs themselves (every row carries the coordinates), so
    the inventory can never disagree with the data.
    """
    rows: list[dict[str, object]] = []
    for climate_id, (name, display_name) in sorted(stations_files.items()):
        data = _read_station_csv(name)
        # the span of actual observations, not of the file: the raw records
        # open with months of empty rows
        observed = data.filter(
            pl.col("precipitation").is_not_null()
            | pl.col("temperature").is_not_null()
        )
        rows.append(
            {
                "climate_id": climate_id,
                "name": display_name,
                "longitude": data["lon"][0],
                "latitude": data["lat"][0],
                "start": observed["datetime"].min(),
                "end": observed["datetime"].max(),
            }
        )

    return pl.DataFrame(
        rows,
        schema={
            "climate_id": pl.String,
            "name": pl.String,
            "longitude": pl.Float64,
            "latitude": pl.Float64,
            "start": pl.Date,
            "end": pl.Date,
        },
    )


def _read_station_csv(name: str) -> pl.DataFrame:
    path = paths.data_dir / "raw" / name
    # the csvs have no public source, so the build layer can only read a
    # copy already on disk (a checkout, or a synced archive)
    if not path.exists():
        raise MissingDataError(
            f"Missing station file {path}; the MELCC csvs have no public "
            "source and must already be on disk."
        )
    # a full schema rather than inference: a record opening with months of
    # empty values would otherwise type its column as strings
    return pl.read_csv(
        path,
        schema={
            "datetime": pl.Date,
            "lat": pl.Float64,
            "lon": pl.Float64,
            "precipitation": pl.Float64,
            "tmax": pl.Float64,
            "tmin": pl.Float64,
            "temperature": pl.Float64,
        },
    )


def _sample_ministry_grid(
    inventory: pl.DataFrame, years: list[int]
) -> pl.DataFrame:
    """The ministry-grid series at the cell over each station.

    A nearest lookup in the grids' native crs, so the cell sampled is the
    one whose footprint contains the station. Years the grids cannot
    supply are skipped; era5 covers them.
    """
    points = gpd.GeoSeries(
        gpd.points_from_xy(
            inventory["longitude"].to_numpy(),
            inventory["latitude"].to_numpy(),
        ),
        crs="EPSG:4326",
    ).to_crs(crs)

    _download_ministry_grid_files(
        [
            f"{parameter}_{year}.nc"
            for year in years
            for parameter in ("PREC", "TMOY")
        ]
    )
    frames: list[pl.DataFrame] = []
    with progress_task(
        "Sampling the ministry grids...",
        f"Sampled {len(years)} ministry grid years.",
        total=len(years),
    ) as current:
        for year in years:
            data = _read_year_ministry_grid_weather_data(year)
            current.increment()
            if data is None:
                continue
            for climate_id, point in zip(inventory["climate_id"], points):
                cell = data.sel(x=point.x, y=point.y, method="nearest")
                frames.append(
                    pl.DataFrame(
                        {
                            "climate_id": climate_id,
                            "datetime": cell["time"].values,
                            "precipitation": cell["precipitation"].values,
                            "temperature": cell["temperature"].values,
                        }
                    ).select(
                        "climate_id",
                        # stamped 05:00; the calendar date is what matches
                        # the station records
                        pl.col("datetime")
                        .cast(pl.Datetime("us"))
                        .dt.date()
                        .cast(pl.Datetime("us")),
                        pl.col("precipitation").fill_nan(None),
                        pl.col("temperature").fill_nan(None),
                    )
                )

    return pl.concat(frames) if frames else _empty_backfill_frame()


def _sample_era5_cells(
    inventory: pl.DataFrame, years: list[int]
) -> pl.DataFrame:
    """The era5 series at the cell containing each station.

    CDS snaps a requested location to the nearest lattice point, so
    rounding to the lattice here means the cached cells are reused as-is.
    """
    station_cells = [
        (
            row["climate_id"],
            _era5_lattice(row["latitude"]),
            _era5_lattice(row["longitude"]),
        )
        for row in inventory.to_dicts()
    ]
    # two stations can share a cell, which is then fetched and read once
    cells = sorted({(lat, lon) for _, lat, lon in station_cells})
    _ensure_era5_cells(cells, years, refetch=False)
    series = _read_era5_years(cells, years)

    return pl.concat(
        [
            series.filter(
                (pl.col("latitude") == latitude)
                & (pl.col("longitude") == longitude)
            ).select(
                pl.lit(climate_id).alias("climate_id"),
                "datetime",
                "precipitation",
                "temperature",
            )
            for climate_id, latitude, longitude in station_cells
        ]
    )


def _coalesce_backfill(
    ministry: pl.DataFrame, era5: pl.DataFrame
) -> pl.DataFrame:
    """Ministry values where the grids have the day, era5 elsewhere.

    era5 is complete over the span, so it fills whatever the grids miss —
    whole-domain missing days and the tail beyond their last stamped day.
    """
    return (
        ministry.join(
            era5,
            on=["climate_id", "datetime"],
            how="full",
            suffix="_era5",
            coalesce=True,
        )
        .select(
            "climate_id",
            "datetime",
            pl.coalesce("precipitation", "precipitation_era5").alias(
                "precipitation"
            ),
            pl.coalesce("temperature", "temperature_era5").alias(
                "temperature"
            ),
        )
        .sort("climate_id", "datetime")
    )


def _read_backfill_product() -> pl.DataFrame:
    path = paths.data_dir / "raw" / stations_backfill_file
    if not path.exists():
        raise MissingDataError(
            f"Missing {path}; run update_stations_backfill first."
        )
    return pl.read_ipc(path, memory_map=False)


def _read_climate_station(climate_id: str) -> pl.DataFrame:
    name, _ = stations_files[climate_id]
    return _read_station_csv(name).select(
        pl.col("datetime").cast(pl.Datetime("us")),
        "precipitation",
        "temperature",
        pl.lit(climate_id).alias("climate_id"),
    )


def _complete_station_series(
    observed: pl.DataFrame, backfill: pl.DataFrame, climate_id: str
) -> pl.DataFrame:
    """Observed values where the station reported, backfill elsewhere.

    Column-wise: a day with only one parameter observed keeps it and takes
    the other from the backfill. The full join keeps observed days outside
    the backfill span, so nothing recorded is ever dropped.
    """
    return (
        observed.drop("climate_id")
        .join(
            backfill.select("datetime", "precipitation", "temperature"),
            on="datetime",
            how="full",
            suffix="_fill",
            coalesce=True,
        )
        .select(
            "datetime",
            pl.coalesce("precipitation", "precipitation_fill").alias(
                "precipitation"
            ),
            pl.coalesce("temperature", "temperature_fill").alias(
                "temperature"
            ),
            pl.lit(climate_id).alias("climate_id"),
        )
        .sort("datetime")
    )


def _read_completed_station_product(climate_id: str) -> pl.DataFrame:
    path = (
        paths.data_dir
        / "raw"
        / "weather"
        / "stations_completed"
        / f"{climate_id}.ipc"
    )
    if not path.exists():
        raise MissingDataError(
            f"Missing {path}; run rebuild_completed_stations first."
        )
    return pl.read_ipc(path, memory_map=False)


def _select_nearest_stations(
    polygons: gpd.GeoDataFrame, inventory: pl.DataFrame, n_stations: int
) -> pl.DataFrame:
    """The n stations closest to each watershed centroid, with IDW weights.

    Shared by the data and grid paths so the stations drawn on the map are
    always the ones actually averaged. Distances are planar metres in the
    polygons' projected crs — degrees would shrink east-west distances at
    48N for the same reason the grid weights are measured projected.
    """
    points = gpd.GeoSeries(
        gpd.points_from_xy(
            inventory["longitude"].to_numpy(),
            inventory["latitude"].to_numpy(),
        ),
        crs="EPSG:4326",
    ).to_crs(polygons.crs)

    rows: list[dict[str, object]] = []
    for i in range(len(polygons)):
        id_ = str(polygons.iloc[i]["id"])
        centroid = polygons.geometry.iloc[i].centroid
        distances = points.distance(centroid).to_numpy()
        for j in np.argsort(distances)[:n_stations]:
            # the metre floor keeps a station sitting on the centroid from
            # taking infinite weight
            distance = max(float(distances[j]), 1.0)
            rows.append(
                {
                    "id": id_,
                    "climate_id": inventory["climate_id"][int(j)],
                    # only an identity key for the client's dedup, like the
                    # grid methods' cell centres
                    "latitude": round(inventory["latitude"][int(j)], 4),
                    "longitude": round(inventory["longitude"][int(j)], 4),
                    "distance": distance,
                    "weight": 1 / distance**2,
                }
            )

    return pl.DataFrame(
        rows,
        schema={
            "id": pl.String,
            "climate_id": pl.String,
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "distance": pl.Float64,
            "weight": pl.Float64,
        },
    )


def _combine_idw(
    selection: pl.DataFrame, series: pl.DataFrame
) -> pl.DataFrame:
    """Inverse-distance mean over each watershed's stations.

    Weights renormalize daily over the stations that reported, so a
    missing station passes its weight to the reporters, and an all-missing
    day comes out null rather than zero.
    """
    combined = (
        selection.select("id", "climate_id", "weight")
        .join(series, on="climate_id", how="inner")
        .group_by("id", "datetime")
        .agg(_idw_mean("precipitation"), _idw_mean("temperature"))
    )
    return _densify_daily(combined).sort("id", "datetime")


def _idw_mean(column: str) -> pl.Expr:
    present = pl.col(column).is_not_null()
    denominator = pl.col("weight").filter(present).sum()
    return (
        pl.when(denominator > 0)
        .then(
            (pl.col(column) * pl.col("weight")).filter(present).sum()
            / denominator
        )
        .otherwise(None)
        .alias(column)
    )


def _densify_daily(data: pl.DataFrame) -> pl.DataFrame:
    """Explicit nulls for days no station has a row for.

    The group_by only yields dates where at least one station reported,
    but `_multiday_gap_mask` needs the missing days present to see the
    runs.
    """
    dense = (
        data.group_by("id")
        .agg(
            pl.datetime_range(
                pl.col("datetime").min(),
                pl.col("datetime").max(),
                interval="1d",
            ).alias("datetime")
        )
        # explicit ahead of the polars 2.0 default flip; the ranges are
        # min..max of existing rows, so they are never empty either way
        .explode("datetime", empty_as_null=True)
    )
    return dense.join(data, on=["id", "datetime"], how="left")


def _trim_null_edges(data: pl.DataFrame) -> pl.DataFrame:
    """Drop each series' leading and trailing not-fully-reported days.

    Edge runs have era5 on one side only (records predate 1940 and outrun
    the era5 product), so they cannot all be backfilled and would later
    crash `_fill_missing`; interior gaps are left as filled.
    """
    complete = (
        pl.col("precipitation").is_not_null()
        & pl.col("temperature").is_not_null()
    )
    return data.filter(
        (complete.cum_sum() > 0).over("id", order_by="datetime")
        & (complete.cum_sum(reverse=True) > 0).over("id", order_by="datetime")
    )


#########
# grids #
#########


def _ministry_grid_grid(polygons: gpd.GeoDataFrame) -> pl.DataFrame:
    """Cells intersecting each watershed, weighted by intersected area.

    The lattice is read from the raster rather than hardcoded, so the
    cells drawn are always the ones actually averaged, even if the grid is
    ever republished on different bounds.
    """
    path = _any_ministry_grid_file()

    # no raster and none reachable: the map simply draws no grid, matching
    # the empty series the data layer returns in the same situation
    if path is None:
        return _empty_grid()

    with xr.open_dataset(path) as data:
        xs = np.asarray(data["x"].values, dtype=np.float64)
        ys = np.asarray(data["y"].values, dtype=np.float64)

    # cell size comes from the spacing, so a half step either side of a
    # centre reconstructs the footprint the file records in x_bnds/y_bnds
    if len(xs) < 2 or len(ys) < 2:
        raise ValueError(
            f"Ministry grid in {path.name} has too few cells to derive a "
            f"cell size from ({len(xs)}x{len(ys)})."
        )
    half_x = abs(float(xs[1] - xs[0])) / 2
    half_y = abs(float(ys[1] - ys[0])) / 2

    rows: list[dict[str, object]] = []

    for i in range(len(polygons)):
        id_ = str(polygons.iloc[i]["id"])
        # the raster is already in crs, so the watershed moves to it rather
        # than the other way round; areas then come out in m2
        watershed = (
            gpd.GeoSeries([polygons.geometry.iloc[i]], crs="EPSG:4326")
            .to_crs(crs)
            .iloc[0]
        )
        min_x, min_y, max_x, max_y = watershed.bounds

        covering_x = xs[(xs + half_x > min_x) & (xs - half_x < max_x)]
        covering_y = ys[(ys + half_y > min_y) & (ys - half_y < max_y)]
        cells = [
            shapely.box(x - half_x, y - half_y, x + half_x, y + half_y)
            for y in covering_y
            for x in covering_x
        ]

        if not cells:
            raise ValueError(
                f"No ministry grid cell intersects watershed {id_}; "
                "check the watershed geometry and its crs."
            )

        projected = gpd.GeoSeries(cells, crs=crs)
        areas = projected.intersection(watershed).area.to_numpy()
        geographic = projected.to_crs("EPSG:4326")

        for j in range(len(cells)):
            if areas[j] <= 0:
                continue
            # only an identity key for the client's dedup; cells are 10 km
            # apart, so four decimals cannot collapse two of them
            centre = geographic.iloc[j].centroid
            rows.append(
                {
                    "id": id_,
                    "latitude": round(centre.y, 4),
                    "longitude": round(centre.x, 4),
                    "weight": float(areas[j]),
                    "geometry": shapely.to_geojson(geographic.iloc[j]),
                }
            )

    return pl.DataFrame(rows, schema=_grid_schema()) if rows else _empty_grid()


def _any_ministry_grid_file() -> Path | None:
    """One GCQ-V3 raster, any year — every year shares the same lattice.

    Prefers a cached file so drawing the grid costs no download; only a
    cache emptied behind a built ministry_grid.ipc has to fetch one.
    """
    directory = paths.data_dir / "raw" / "weather" / "ministry_grid"
    cached = sorted(directory.glob("PREC_*.nc"))

    if cached:
        return cached[0]

    return _ministry_grid_file(f"PREC_{ministry_grid_start_year}.nc")


def _nearest_stations_grid(polygons: gpd.GeoDataFrame) -> pl.DataFrame:
    """The stations nearest each watershed, as points for the map.

    Always the closest max_n_stations, so the client can show the whole
    pool and link however many the slider selects; sorting by weight
    recovers the selection order, since both come from
    _select_nearest_stations.
    """
    inventory = _read_station_inventory()
    selection = _select_nearest_stations(
        polygons.to_crs(crs), inventory, max_n_stations
    )

    if selection.is_empty():
        return _empty_grid()

    # identity and record span ride along so the client can grey out the
    # stations outside the chosen periods and label the popups
    meta = {
        row["climate_id"]: row
        for row in inventory.select(
            "climate_id", "name", "start", "end"
        ).to_dicts()
    }
    return pl.DataFrame(
        [
            {
                "id": row["id"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "weight": row["weight"],
                "geometry": shapely.to_geojson(
                    shapely.Point(row["longitude"], row["latitude"])
                ),
                "climate_id": row["climate_id"],
                "name": meta[row["climate_id"]]["name"],
                "start": meta[row["climate_id"]]["start"],
                "end": meta[row["climate_id"]]["end"],
            }
            for row in selection.to_dicts()
        ],
        schema=_grid_schema(),
    )


def _grid_schema() -> dict[str, pl.DataType]:
    # the last four are nearest_stations-only; the raster methods leave
    # them null and the client only reads them for station points
    return {
        "id": pl.String(),
        "latitude": pl.Float64(),
        "longitude": pl.Float64(),
        "weight": pl.Float64(),
        "geometry": pl.String(),
        "climate_id": pl.String(),
        "name": pl.String(),
        "start": pl.Date(),
        "end": pl.Date(),
    }


def _empty_grid() -> pl.DataFrame:
    return pl.DataFrame(schema=_grid_schema())


def _empty_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "id": pl.String,
            "datetime": pl.Datetime,
            "precipitation": pl.Float64,
            "temperature": pl.Float64,
        }
    )


def _empty_backfill_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "climate_id": pl.String,
            "datetime": pl.Datetime("us"),
            "precipitation": pl.Float64,
            "temperature": pl.Float64,
        }
    )
