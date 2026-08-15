import concurrent.futures
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from typing import Literal, assert_never

import cdsapi
import exactextract
import geopandas as gpd
import httpx
import numpy as np
import numpy.typing as npt
import polars as pl
import shapely
import xarray as xr

from holmes.utils.paths import data_dir
from holmes.utils.print import done_print, load_print, load_progress

#########
# types #
#########

WeatherMethod = Literal["nearest_stations", "era5", "ministry_grid"]

#############
# constants #
#############

# ERA5 is served on a regular 0.25 deg lat-lon grid; requests snap to it, so
# generating cell centres on the same lattice means one request per cell
era5_resolution = 0.25

# streamflow is on local calendar days, so the hourly UTC series is converted
# before the daily reduction rather than after
local_timezone = "America/Montreal"

# CDS throttles concurrent requests per user; four keeps a cold cache moving
# without tripping the limit
era5_max_workers = 4

# ERA5 begins in 1940, but station 061004 records from 1910; asking for the
# earlier years errors, so requests are clamped. CDS clips the recent end on
# its own, following the few-day reanalysis lag.
era5_start_year = 1940

# The MELCC daily station files behind nearest_stations were hand-delivered
# for the TP and have no public source; ids, names and coordinates come from
# the RSCQ open-data station list and the 1991-2020 climate normals.
# `scripts/convert_stations.py` regenerates the csvs from the raw files.
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
# station's era5 cell otherwise. Built by `holmes download` from the raster
# caches (gigabytes nothing else needs), committed like era5.ipc.
stations_backfill_file = "weather/stations_backfill.ipc"

# Everything else in the data layer is rebuilt from its true source at
# runtime. era5 cannot be: it needs a Copernicus account. Nor can the station
# csvs: their raw files are not published anywhere. So the finished products
# are committed to the repo and downloaded from there instead of shipping in
# the wheel, which stays data-free.
published_base_url = (
    "https://raw.githubusercontent.com/antoinelb/holmes/main/data/raw/"
)
published_files = (
    "weather/era5.ipc",
    stations_backfill_file,
    *(name for name, _ in stations_files.values()),
)

# the big prebuilt products (era5.ipc and the projection products) are also
# published as assets on the repo's rolling `data` release (`make
# upload-assets`): reads try these before the committed copy or a rebuild,
# and git blobs never have to carry the projection products at all
release_assets_base_url = (
    "https://github.com/antoinelb/holmes/releases/download/data/"
)

# the GCQ-V3 daily climate grids, published as one NetCDF per parameter and
# year. The dataset page lists an index CSV of these same links, but it is
# served from this host too, so reading it would add a request without adding
# resilience.
# https://www.donneesquebec.ca/recherche/dataset/rscq_grilles_climatiques_version_3
ministry_grid_base_url = (
    "https://stqc380donopppdtce01.blob.core.windows.net/donnees-ouvertes/"
    "Climat/Analyses/Grilles_climatiques/Quotidien/NetCDF/"
)

# the grids start in 1940, but station 061004 records from 1910; the earlier
# years simply do not exist, so requests are clamped like era5's
ministry_grid_start_year = 1940

# grid downloads are network-bound and independent, so a cold cache fetches
# them concurrently; four is polite to the ministry's blob store
ministry_grid_max_workers = 4

# nearest-station picks are bounded by the UI slider
min_n_stations = 1
max_n_stations = 5

##########
# public #
##########


def read_weather_data(
    stations: pl.DataFrame,
    *,
    method: WeatherMethod,
    n_stations: int = 3,
    rebuild: bool = False,
) -> pl.DataFrame:
    _validate_n_stations(n_stations)
    crs = "EPSG:32198"

    # the station count changes the nearest-stations product, so it is part
    # of its cache name; the grid methods ignore it
    name = (
        f"weather/nearest_stations_{n_stations}.ipc"
        if method == "nearest_stations"
        else f"weather/{method}.ipc"
    )
    path = data_dir / "raw" / name

    # rebuild is the maintainer path (`holmes download`): it regenerates from the
    # true source the file the app would otherwise be content to fetch, so
    # both shortcuts below are skipped
    if not rebuild:
        # a published product is downloaded rather than rebuilt; a failure
        # falls through to the next source rather than raising
        if not path.exists() and method == "era5":
            download_release_asset("era5.ipc", path)
        if not path.exists() and name in published_files:
            download_published_file(name)

        if path.exists():
            # memory mapping is unavailable on the compressed cache and warns
            # loudly about it; the read costs ~20 ms either way
            return pl.read_ipc(path, memory_map=False)

    max_year = date.today().year
    years = sorted(
        set().union(
            *(
                range(
                    row["start"],
                    (row["end"] if row["end"] is not None else max_year) + 1,
                )
                for row in stations.select("start", "end").to_dicts()
            )
        )
    )
    polygons = _to_geopandas(stations).to_crs(crs)

    match method:
        case "nearest_stations":
            data = _read_nearest_stations_weather_data(polygons, n_stations)
            # the per-station completion leaves the series dense, but the
            # edges can still be incomplete (the backfill sources start and
            # stop on different days), and an unfillable edge run would
            # crash `_fill_missing`
            data = _trim_null_edges(data)
        case "era5":
            data = _read_era5_weather_data(
                polygons,
                max(min(years), era5_start_year),
                max(years),
                crs=crs,
            )
        case "ministry_grid":
            data = _read_ministry_grid_weather_data(
                polygons,
                [y for y in years if y >= ministry_grid_start_year],
                crs=crs,
            )
            # the source grids have whole-domain missing days that era5
            # does not; a run of two or more adjacent nulls would later
            # make model calibration raise (`_fill_missing` interpolates
            # only isolated gaps), so multi-day runs are backfilled from
            # the complete era5 series while single-day gaps are left for
            # that interpolation. Recursing here reads the cached era5.ipc
            # rather than rebuilding it, and the era5 case never re-enters
            # this branch.
            data = _fill_multiday_gaps_from_era5(
                data, read_weather_data(stations, method="era5")
            )
        case _:  # pragma: no cover
            assert_never(method)

    # era5.ipc is committed, so it is worth compressing: zstd takes it
    # from 10 MB to 4 MB, and git stores a new blob on every rebuild
    path.parent.mkdir(exist_ok=True, parents=True)
    data.write_ipc(path, compression="zstd")

    return data


def download_release_asset(asset: str, path: Path) -> bool:
    """Download one release asset to `path`, returning whether it succeeded.

    Never raises: callers fall back to the next source (a committed copy or
    a rebuild), which reports its own missing prerequisites.
    """
    try:
        response = httpx.get(
            release_assets_base_url + asset,
            timeout=300.0,
            follow_redirects=True,
        )
        response.raise_for_status()

        path.parent.mkdir(exist_ok=True, parents=True)
        # a truncated body or an error page would otherwise be cached as if
        # it were data and fail on every later read
        staged = path.with_suffix(".part")
        staged.write_bytes(response.content)
        pl.read_ipc(staged, memory_map=False)
        staged.replace(path)

        done_print(f"Downloaded {asset}")
        return True

    except Exception as exc:
        load_print(f"Could not download {asset} ({exc})", end="\n")
        return False


def download_published_file(name: str) -> bool:
    """Download one published dataset, returning whether it succeeded.

    Never raises: callers fall back to rebuilding from the true source, which
    reports its own missing prerequisites.
    """
    if name not in published_files:
        raise ValueError(
            f"Unknown published dataset {name}; expected one of "
            f"{', '.join(published_files)}."
        )

    path = data_dir / "raw" / name

    try:
        response = httpx.get(
            published_base_url + name, timeout=300.0, follow_redirects=True
        )
        response.raise_for_status()

        path.parent.mkdir(exist_ok=True, parents=True)
        # a truncated body, or the html error page raw.githubusercontent
        # serves for a path missing on the branch, would otherwise be cached
        # as if it were data and fail on every later read
        staged = path.with_suffix(".part")
        staged.write_bytes(response.content)
        if path.suffix == ".csv":
            pl.read_csv(staged)
        else:
            pl.read_ipc(staged, memory_map=False)
        staged.replace(path)

        done_print(f"Downloaded {name}")
        return True

    except Exception as exc:
        load_print(f"Could not download {name} ({exc})", end="\n")
        return False


def rebuild_stations_backfill() -> pl.DataFrame:
    """Rebuild the committed per-station backfill from the raster caches.

    The maintainer path behind `holmes download`. For each station: the ministry
    grid sampled at the cell containing the station (nearest lookup in the
    grids' native EPSG:32198), and, for the days the grids miss, the era5
    cell containing the station. Needs the ministry NetCDFs (downloaded on a
    miss, gigabytes) and the era5 cell caches (CDS credentials only if a
    cell is genuinely missing).
    """
    crs = "EPSG:32198"
    inventory = _read_station_inventory()
    years = range(ministry_grid_start_year, date.today().year + 1)

    ministry = _sample_ministry_grid(inventory, years, crs=crs)
    era5 = _sample_era5_cells(inventory, min(years), max(years))

    # era5 is complete over the span, so it fills whatever the grids miss —
    # whole-domain missing days and the tail beyond their last stamped day
    backfill = (
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

    path = data_dir / "raw" / stations_backfill_file
    path.parent.mkdir(exist_ok=True, parents=True)
    backfill.write_ipc(path, compression="zstd")
    done_print(f"Rebuilt {stations_backfill_file}")

    return backfill


def read_weather_grid(
    stations: pl.DataFrame, *, method: WeatherMethod
) -> pl.DataFrame:
    """Cells or stations feeding each watershed mean, for the map.

    Called after read_weather_data and sent in the same reply, so the rasters
    a method needs are already cached by the time this runs.
    """
    polygons = _to_geopandas(stations)

    match method:
        case "era5":
            return _era5_grid(polygons, crs="EPSG:32198")
        case "ministry_grid":
            return _ministry_grid_grid(polygons, crs="EPSG:32198")
        # nearest_stations reads point series, so its "grid" is the nearby
        # stations themselves; always the full pool, whatever the slider says
        case "nearest_stations":
            return _nearest_stations_grid(polygons, crs="EPSG:32198")
        case _:  # pragma: no cover
            assert_never(method)


###########
# private #
###########


def _to_geopandas(stations: pl.DataFrame) -> gpd.GeoDataFrame:
    """Watershed polygons (WKB geometry column) as a geopandas frame."""
    return gpd.GeoDataFrame(
        {"id": stations["id"].to_list()},
        geometry=gpd.GeoSeries.from_wkb(stations["geometry"].to_list()),
        crs="EPSG:4326",
    )


####################
# nearest stations #
####################


def _validate_n_stations(n_stations: int) -> None:
    if not min_n_stations <= n_stations <= max_n_stations:
        raise ValueError(
            f"n_stations must be between {min_n_stations} and "
            f"{max_n_stations}, got {n_stations}."
        )


def _read_nearest_stations_weather_data(
    polygons: gpd.GeoDataFrame, n_stations: int
) -> pl.DataFrame:
    inventory = _read_station_inventory()
    selection = _select_nearest_stations(polygons, inventory, n_stations)

    if selection.is_empty():
        return _empty_frame()

    # a station shared by two watersheds is read once and joined twice
    series = _read_climate_stations(
        sorted(set(selection["climate_id"].to_list()))
    )
    return _combine_idw(selection, series)


def _read_station_inventory() -> pl.DataFrame:
    """The MELCC stations: identifier, name, location and record span.

    Built from the published csvs themselves (every row carries the
    coordinates), so the inventory can never disagree with the data.
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
    path = data_dir / "raw" / name
    # present in a checkout; an installed copy fetches it from the repo
    if not path.exists():
        download_published_file(name)
    if not path.exists():
        raise RuntimeError(
            f"Station file {name} is missing and could not be downloaded."
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
    inventory: pl.DataFrame, years: range, *, crs: str
) -> pl.DataFrame:
    """The ministry-grid series at the cell over each station.

    A nearest lookup in the grids' native crs, so the cell sampled is the
    one whose footprint contains the station. Years the grids cannot supply
    are skipped; era5 covers them.
    """
    points = gpd.GeoSeries(
        gpd.points_from_xy(
            inventory["longitude"].to_numpy(),
            inventory["latitude"].to_numpy(),
        ),
        crs="EPSG:4326",
    ).to_crs(crs)

    frames: list[pl.DataFrame] = []
    _download_ministry_grid_files(
        [
            f"{parameter}_{year}.nc"
            for year in years
            for parameter in ("PREC", "TMOY")
        ]
    )
    for year in load_progress(
        list(years), "Sampling ministry grids...", total=len(years)
    ):
        data = _read_year_ministry_grid_weather_data(year, crs=crs)
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
                    # stamped 05:00; the calendar date is what matches the
                    # station records
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
    inventory: pl.DataFrame, start_year: int, end_year: int
) -> pl.DataFrame:
    """The era5 series at the cell containing each station.

    CDS snaps a requested location to the nearest lattice point, so rounding
    to the lattice here means the cached cells are reused as-is.
    """
    cells = [
        (
            row["climate_id"],
            _era5_lattice(row["latitude"]),
            _era5_lattice(row["longitude"]),
        )
        for row in inventory.to_dicts()
    ]
    # like _download_era5_cells: every missing cell would fail the same way,
    # so the credentials are checked once with actionable instructions
    if any(
        not _era5_cell_path(lat, lon, start_year, end_year).exists()
        for _, lat, lon in cells
    ):
        _check_era5_credentials()

    return pl.concat(
        [
            _read_era5_cell(lat, lon, start_year, end_year).select(
                pl.lit(climate_id).alias("climate_id"),
                "datetime",
                "precipitation",
                "temperature",
            )
            for climate_id, lat, lon in cells
        ]
    )


def _era5_lattice(value: float) -> float:
    return round(round(value / era5_resolution) * era5_resolution, 2)


def _empty_backfill_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "climate_id": pl.String,
            "datetime": pl.Datetime("us"),
            "precipitation": pl.Float64,
            "temperature": pl.Float64,
        }
    )


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


def _read_climate_stations(climate_ids: list[str]) -> pl.DataFrame:
    return pl.concat(
        [_read_completed_station(climate_id) for climate_id in climate_ids]
    )


def _read_completed_station(climate_id: str) -> pl.DataFrame:
    """One station's record, completed from the published backfill.

    The observed record is completed column-wise — the ministry-grid cell
    over the station, era5's where the grids miss the day — so every
    station covers the whole reference span and any period can be
    simulated. Completion happens once, when the station data is first
    obtained (right after download in an installed copy), and the result
    is cached; the published csv stays raw because the inventory derives
    the true observed span from it.
    """
    path = (
        data_dir
        / "raw"
        / "weather"
        / "stations_completed"
        / f"{climate_id}.ipc"
    )
    if path.exists():
        return pl.read_ipc(path, memory_map=False)

    completed = _complete_station_series(
        _read_climate_station(climate_id),
        _read_stations_backfill().filter(pl.col("climate_id") == climate_id),
        climate_id,
    )
    path.parent.mkdir(exist_ok=True, parents=True)
    completed.write_ipc(path, compression="zstd")
    return completed


def _read_climate_station(climate_id: str) -> pl.DataFrame:
    name, _ = stations_files[climate_id]
    return _read_station_csv(name).select(
        pl.col("datetime").cast(pl.Datetime("us")),
        "precipitation",
        "temperature",
        pl.lit(climate_id).alias("climate_id"),
    )


def _read_stations_backfill() -> pl.DataFrame:
    path = data_dir / "raw" / stations_backfill_file
    # present in a clone; an installed copy fetches it from the repo
    if not path.exists():
        download_published_file(stations_backfill_file)
    if not path.exists():
        raise RuntimeError(
            f"{stations_backfill_file} is missing and could not be "
            "downloaded; `holmes download` rebuilds it from the raster caches."
        )
    return pl.read_ipc(path, memory_map=False)


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


def _combine_idw(
    selection: pl.DataFrame, series: pl.DataFrame
) -> pl.DataFrame:
    """Inverse-distance mean over each watershed's stations.

    Weights renormalize daily over the stations that reported, so a missing
    station passes its weight to the reporters, and an all-missing day comes
    out null rather than zero.
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

    The group_by only yields dates where at least one station reported, but
    `_multiday_gap_mask` needs the missing days present to see the runs.
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
    the committed era5.ipc), so they cannot all be backfilled and would
    later crash `_fill_missing`; interior gaps are left as filled.
    """
    complete = (
        pl.col("precipitation").is_not_null()
        & pl.col("temperature").is_not_null()
    )
    return data.filter(
        (complete.cum_sum() > 0).over("id", order_by="datetime")
        & (complete.cum_sum(reverse=True) > 0).over("id", order_by="datetime")
    )


def _nearest_stations_grid(
    polygons: gpd.GeoDataFrame, *, crs: str
) -> pl.DataFrame:
    """The stations nearest each watershed, as points for the map.

    Always the closest max_n_stations, so the client can show the whole pool
    and link however many the slider selects; sorting by weight recovers the
    selection order, since both come from _select_nearest_stations.
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


#########
# era5 #
#########


def _read_era5_weather_data(
    polygons: gpd.GeoDataFrame, start_year: int, end_year: int, *, crs: str
) -> pl.DataFrame:
    grid = _era5_grid(polygons.to_crs("EPSG:4326"), crs=crs)

    if grid.is_empty():
        return _empty_frame()

    cells = (
        grid.select("latitude", "longitude")
        .unique()
        .sort("latitude", "longitude")
    )
    series = _download_era5_cells(cells, start_year, end_year)

    # the weighted mean is over the cells covering each watershed, so a cell
    # shared by two watersheds is downloaded once and joined twice
    return (
        grid.join(series, on=["latitude", "longitude"], how="inner")
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


def _era5_grid(polygons: gpd.GeoDataFrame, *, crs: str) -> pl.DataFrame:
    """Cells intersecting each watershed, weighted by intersected area.

    Areas are measured in the projected crs: a 0.25 deg cell at 48N is far
    taller than it is wide, so intersecting in degrees would over-weight the
    northern cells.
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
    snaps a requested location, so the centres double as request coordinates.
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


def _download_era5_cells(
    cells: pl.DataFrame, start_year: int, end_year: int
) -> pl.DataFrame:
    coordinates = [
        (row["latitude"], row["longitude"]) for row in cells.to_dicts()
    ]

    # every cell would otherwise fail the same way deep inside the pool, so
    # the credentials are checked once, up front, with a message that says
    # what to do about it
    missing = [
        (latitude, longitude)
        for latitude, longitude in coordinates
        if not _era5_cell_path(
            latitude, longitude, start_year, end_year
        ).exists()
    ]
    if missing:
        _check_era5_credentials()

    # requests are network-bound and independent, so they overlap; the pool is
    # bounded because CDS rejects too many concurrent jobs
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=era5_max_workers
    ) as pool:
        data = list(
            load_progress(
                pool.map(
                    lambda coordinate: _read_era5_cell(
                        coordinate[0], coordinate[1], start_year, end_year
                    ),
                    coordinates,
                ),
                "Reading ERA5 data...",
                total=len(coordinates),
            )
        )

    return pl.concat(data)


def _check_era5_credentials() -> None:
    try:
        cdsapi.Client()
    except Exception as exc:
        raise RuntimeError(
            f"No ERA5 data at {_era5_cache_path()} and it could not be "
            "fetched from the repo, so it has to be rebuilt from source. "
            "That needs a Copernicus account: register at "
            "https://cds.climate.copernicus.eu, accept the ERA5 licence, "
            "then put your personal access token in ~/.cdsapirc:\n"
            "  url: https://cds.climate.copernicus.eu/api\n"
            "  key: <your-token>"
        ) from exc


def _era5_cache_path() -> Path:
    return data_dir / "raw" / "weather" / "era5.ipc"


def _era5_cell_path(
    latitude: float, longitude: float, start_year: int, end_year: int
) -> Path:
    return (
        data_dir
        / "raw"
        / "weather"
        / "era5"
        / f"{latitude:.2f}_{longitude:.2f}_{start_year}_{end_year}.ipc"
    )


def _read_era5_cell(
    latitude: float, longitude: float, start_year: int, end_year: int
) -> pl.DataFrame:
    path = _era5_cell_path(latitude, longitude, start_year, end_year)
    if path.exists():
        return pl.read_ipc(path)

    data = _reduce_era5_cell(
        _download_era5_cell(latitude, longitude, start_year, end_year),
        latitude,
        longitude,
    )
    path.parent.mkdir(exist_ok=True, parents=True)
    data.write_ipc(path)

    return data


def _download_era5_cell(
    latitude: float, longitude: float, start_year: int, end_year: int
) -> pl.DataFrame:
    """Hourly series at one grid point, extracted server-side by CDS.

    The timeseries dataset returns a small csv per point rather than a
    gridded field, so decades of hourly data cost a few MB per cell.
    """
    client = cdsapi.Client()

    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / "cell.zip"
        client.retrieve(
            "reanalysis-era5-single-levels-timeseries",
            {
                "variable": ["2m_temperature", "total_precipitation"],
                "date": [f"{start_year}-01-01/{end_year}-12-31"],
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

    ERA5 stamps each hourly accumulation at the *end* of the hour it covers,
    so the 00:00 stamp belongs to the previous day; shifting back an hour
    before taking the date puts every value on the day it fell. Note this is
    the ERA5 convention — ERA5-Land instead accumulates from 00 UTC, and
    summing that would inflate totals roughly twelvefold.
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


#################
# ministry grid #
#################


def _read_ministry_grid_weather_data(
    polygons: gpd.GeoDataFrame, years: list[int], *, crs: str
) -> pl.DataFrame:
    weights: (
        dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]] | None
    ) = None
    data: list[pl.DataFrame] = []

    _download_ministry_grid_files(
        [
            f"{parameter}_{year}.nc"
            for year in years
            for parameter in ("PREC", "TMOY")
        ]
    )
    for year in load_progress(years, "Reading weather data..."):
        weather = _read_year_ministry_grid_weather_data(year, crs=crs)

        if weather is None:
            continue

        if weights is None:
            weights = _compute_coverage_weights(polygons, weather)

        data.append(_reduce_year(polygons["id"], weather, weights))

    if data:
        return pl.concat(data, how="diagonal").sort("id", "datetime")
    else:
        return pl.DataFrame(
            schema={
                "id": pl.String,
                "datetime": pl.Datetime,
                "precipitation": pl.Float64,
                "temperature": pl.Float64,
            }
        )


def _fill_multiday_gaps_from_era5(
    data: pl.DataFrame, era5: pl.DataFrame
) -> pl.DataFrame:
    reference = era5.select(
        "id",
        pl.col("datetime").dt.date().alias("date"),
        pl.col("precipitation").alias("era5_precipitation"),
        pl.col("temperature").alias("era5_temperature"),
    )
    # era5 is stamped at 00:00 and the grids at 05:00, so the join is on the
    # calendar date rather than the raw datetime
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

    A single missing day has present neighbours on both sides, so it is left
    for `_fill_missing` to interpolate; any longer run has at least one
    missing neighbour, which is what marks it for the era5 backfill.
    """
    is_missing = pl.col(column).fill_nan(None).is_null()
    return (
        is_missing
        & (
            is_missing.shift(1, fill_value=False)
            | is_missing.shift(-1, fill_value=False)
        )
    ).over("id", order_by="datetime")


def _read_year_ministry_grid_weather_data(
    year: int, *, crs: str
) -> xr.Dataset | None:
    # only the two parameters the models need; the dataset also publishes
    # TMIN and TMAX, which nothing here reads
    precipitation_path = _ministry_grid_file(f"PREC_{year}.nc")
    mean_temperature_path = _ministry_grid_file(f"TMOY_{year}.nc")

    # a year that could not be fetched is skipped rather than fatal: the rest
    # of the record still makes a usable series
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


def _ministry_grid_grid(
    polygons: gpd.GeoDataFrame, *, crs: str
) -> pl.DataFrame:
    """Cells intersecting each watershed, weighted by intersected area.

    The lattice is read from the raster rather than hardcoded, so the cells
    drawn are always the ones actually averaged, even if the grid is ever
    republished on different bounds.
    """
    path = _any_ministry_grid_file()

    # no raster and none reachable: the map simply draws no grid, matching
    # the empty series read_weather_data returns in the same situation
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

    Prefers a cached file so drawing the grid costs no download; only a cache
    emptied behind a built ministry_grid.ipc has to fetch one.
    """
    directory = data_dir / "raw" / "weather" / "ministry_grid"
    cached = sorted(directory.glob("PREC_*.nc"))

    if cached:
        return cached[0]

    return _ministry_grid_file(f"PREC_{ministry_grid_start_year}.nc")


def _download_ministry_grid_files(names: list[str]) -> None:
    """Fetch the missing grid files concurrently before they are read.

    The year loops then hit warm files. Threads rather than the asyncio
    pattern because `read_weather_data` is sync and sometimes already runs
    on an event loop (`experiment.read_data`), where an internal
    `asyncio.run` would raise. `_ministry_grid_file` stages each file
    individually, so concurrent downloads of distinct names are safe, and
    a file that cannot be fetched stays missing: its year is skipped by
    the caller as before.
    """
    missing = [
        name
        for name in names
        if not (data_dir / "raw" / "weather" / "ministry_grid" / name).exists()
    ]
    if not missing:
        return
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=ministry_grid_max_workers
    ) as pool:
        list(
            load_progress(
                pool.map(_ministry_grid_file, missing),
                "Downloading ministry grids...",
                total=len(missing),
            )
        )


def _ministry_grid_file(name: str) -> Path | None:
    """Path to one GCQ-V3 NetCDF, downloading it first if it is missing.

    Returns None when it is neither cached nor reachable, so a single bad
    year does not abort the whole read.
    """
    path = data_dir / "raw" / "weather" / "ministry_grid" / name

    if path.exists():
        return path

    try:
        response = httpx.get(
            ministry_grid_base_url + name,
            timeout=300.0,
            follow_redirects=True,
        )
        response.raise_for_status()

        path.parent.mkdir(exist_ok=True, parents=True)
        # a truncated body, or an error page served in place of the file,
        # would otherwise be cached as if it were data and fail on every
        # later read
        staged = path.with_suffix(".part")
        staged.write_bytes(response.content)
        xr.open_dataset(staged).close()
        staged.replace(path)

        done_print(f"Downloaded {name}")
        return path

    except Exception as exc:
        load_print(f"Could not download {name} ({exc})", end="\n")
        return None


def _compute_coverage_weights(
    polygons: gpd.GeoDataFrame, weather_grid: xr.Dataset
) -> dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]]:
    coverage = exactextract.exact_extract(
        weather_grid["precipitation"].isel(time=0),
        polygons,
        ["cell_id", "coverage"],
        output="pandas",
    )
    return {
        polygons.iloc[i]["id"]: (
            np.asarray(coverage.iloc[i]["cell_id"], dtype=np.int64),
            np.asarray(coverage.iloc[i]["coverage"], dtype=np.float64),
        )
        for i in range(len(coverage))
    }


def _reduce_year(
    ids: pl.Series,
    weather: xr.Dataset,
    weights: dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]],
) -> pl.DataFrame:
    n_time = weather.sizes["time"]
    n_cells = weather.sizes["y"] * weather.sizes["x"]

    precipitation = weather["precipitation"].values.reshape(n_time, n_cells)
    temperature = weather["temperature"].values.reshape(n_time, n_cells)
    datetime = pl.Series(
        "datetime", weather.time.to_numpy()
    ).dt.cast_time_unit("us")

    data: list[pl.DataFrame] = []

    for id_ in ids:
        cell_ids, coverage = weights[id_]
        data.append(
            pl.DataFrame(
                {
                    "datetime": datetime,
                    "precipitation": _calculate_masked_mean(
                        precipitation, cell_ids, coverage
                    ),
                    "temperature": _calculate_masked_mean(
                        temperature, cell_ids, coverage
                    ),
                }
            ).with_columns(pl.lit(id_).alias("id"))
        )
    return pl.concat(data)


def _calculate_masked_mean(
    values: npt.NDArray[np.float64],
    cells: npt.NDArray[np.int64],
    weights: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    covered = values[:, cells]
    mask = ~np.isnan(covered)
    denominator = np.where(mask, weights, 0.0).sum(axis=1)
    numerator = np.where(mask, covered * weights, 0.0).sum(axis=1)
    return np.where(
        denominator > 0,
        numerator / np.where(denominator == 0, 1.0, denominator),
        np.nan,
    )


def _empty_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "id": pl.String,
            "datetime": pl.Datetime,
            "precipitation": pl.Float64,
            "temperature": pl.Float64,
        }
    )


def _grid_schema() -> dict[str, pl.DataType]:
    # the last four are nearest_stations-only; the raster methods leave them
    # null and the client only reads them for station points
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
