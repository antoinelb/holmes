"""Build layer for the hydrometric products.

Copies of the loaders in `holmes.data.hydro`, adapted for the sync
`holmes download` orchestrator: skip-if-exists products, staged writes,
and task-style printing. The originals stay in place until the final
cleanup pass.
"""

import re
import shutil
import zipfile
from pathlib import Path
from typing import cast

import geopandas as gpd
import httpx
import polars as pl
import pyproj
import rioxarray
import shapely
import shapely.ops
import xarray as xr
from pystac_client import Client
from rioxarray.merge import merge_arrays

# STATIONS stays in the data layer for now: single source of truth until
# the final cleanup pass moves it into the build layer
from holmes.data.hydro import STATIONS

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths
from holmes.utils.print import progress_task, task, warn_print

#############
# constants #
#############

stations_url = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "c31e2bee-a899-46ca-ad84-5798f0f49676/resource/"
    "6b2d32ef-80e2-445b-9bd1-97ddc39b5d59/download/"
    "stations_hydrometriques.csv"
)

open_watersheds_url = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "c31e2bee-a899-46ca-ad84-5798f0f49676/resource/"
    "924cce0a-5fcc-47fa-a725-5ec84522090f/download/"
    "bassins_versants_stations_ouvertes.zip"
)

closed_watersheds_url = (
    "https://www.donneesquebec.ca/recherche/dataset/"
    "c31e2bee-a899-46ca-ad84-5798f0f49676/resource/"
    "8020bb47-8124-4cc2-a5ad-e2c312e7c7cf/download/"
    "bv_stations_fermees.zip"
)

streamflow_url = (
    "https://www.cehq.gouv.qc.ca/depot/historique_donnees/fichier/{id}_Q.txt"
)

streamflow_row_regex = re.compile(
    r"(\d+)\s+(\d{4}/\d{2}/\d{2})(?:\s+(-?\d+(?:\.\d+)?))?"
)
streamflow_area_regex = re.compile(r"Bassin versant:\s*([\d.,]+)\s*km")

##########
# public #
##########


def build_station_data(*, force: bool = False) -> pl.DataFrame:
    """Station metadata joined with the watershed and DEM products.

    Skip-if-exists: a cached `station_data.ipc` is read back unless
    `force`, in which case every stage refetches from its true source.
    """
    path = paths.data_dir / "raw" / "hydro" / "station_data.ipc"
    if path.exists() and not force:
        return pl.read_ipc(path, memory_map=False)
    with task("Building station data...", "Built station data."):
        stations = _rename_stations(_get_stations(force=force))
        watersheds = _get_watersheds(stations, force=force)
        data = stations.join(watersheds, on="id", how="left")
        _write_ipc(data, path)
    return data


def fetch_streamflow(stations: pl.DataFrame, *, force: bool = False) -> None:
    """Refetch the full CEHQ streamflow file of every station.

    The source updates continuously and the files stay small (≤ ~1.2 MB),
    so whole files are the accepted refetch granularity. A file already
    fetched today is left alone unless `force`. A failed fetch keeps a
    previous file with a warning, but raises when no previous file
    exists: the archive would otherwise miss a product.
    """
    if "id" not in stations.columns or stations.height == 0:
        raise ValueError("No stations to fetch streamflow for.")

    ids = stations["id"].to_list()
    with (
        progress_task(
            "Fetching streamflow...", "Fetched streamflow.", total=len(ids)
        ) as progress,
        httpx.Client(timeout=60.0) as client,
    ):
        for id in ids:
            path = (
                paths.data_dir / "raw" / "hydro" / "streamflow" / f"{id}.ipc"
            )
            if not force and paths.fetched_today(path):
                progress.increment()
                continue
            try:
                data = _fetch_station_streamflow(client, id)
            # PolarsError covers parse failures past the regexes, e.g. a
            # row whose date matches the format but is not a real date
            except (
                httpx.HTTPError,
                ValueError,
                pl.exceptions.PolarsError,
            ) as exc:
                if path.exists():
                    warn_print(
                        f"Could not refresh streamflow for {id} ({exc}); "
                        "keeping the previous file."
                    )
                    progress.increment()
                    continue
                raise RuntimeError(
                    f"Could not fetch streamflow for {id} and no previous "
                    f"file exists ({exc})."
                ) from exc
            _write_ipc(data, path)
            progress.increment()


###########
# private #
###########


def _get_stations(*, force: bool) -> pl.DataFrame:
    path = paths.data_dir / "raw" / "hydro" / "stations.ipc"
    if path.exists() and not force:
        return pl.read_ipc(path, memory_map=False)
    with task("Downloading stations...", "Downloaded stations."):
        stations = pl.read_csv(
            stations_url, schema_overrides={"no": pl.String}
        ).select(
            pl.col("no").alias("id"),
            pl.col("nom").alias("name"),
            "type",
            pl.col("latitude").alias("lat"),
            pl.col("longitude").alias("lon"),
            pl.col("debut").cast(pl.Int64, strict=False).alias("start"),
            pl.col("fin").cast(pl.Int64, strict=False).alias("end"),
            pl.col("cours_eau").alias("waterway"),
            pl.col("superficie").alias("area"),
            (pl.col("etat") == "Ouverte").alias("open"),
        )
        stations = stations.filter(pl.col("id").is_in(STATIONS))
        _write_ipc(stations, path)
    return stations


def _rename_stations(stations: pl.DataFrame) -> pl.DataFrame:
    # friendlier names the rest of the code and the experiments match on
    return stations.with_columns(
        pl.when(pl.col("id") == "061028")
        .then(pl.lit("Pikauba Aval"))
        .when(pl.col("id") == "061022")
        .then(pl.lit("Pikauba Amont"))
        .otherwise(pl.col("name"))
        .alias("name")
    )


def _get_watersheds(stations: pl.DataFrame, *, force: bool) -> pl.DataFrame:
    path = paths.data_dir / "raw" / "hydro" / "watersheds" / "watersheds.ipc"
    if path.exists() and not force:
        return pl.read_ipc(path, memory_map=False)
    watersheds = _download_watersheds(force=force)
    data = stations.select("id").join(watersheds, on="id", how="left")
    # the wkb is the only stored form: a second geojson copy of the same
    # polygons cost more of the archive than every weather product
    # combined, and the server already parses the wkb for its centroids
    dem = _get_dem_data(data, force=force)
    data = data.join(dem, on="id", how="left")
    _write_ipc(data, path)
    return data


def _download_watersheds(*, force: bool) -> pl.DataFrame:
    open_path = (
        paths.data_dir
        / "raw"
        / "hydro"
        / "watersheds"
        / "open"
        / "watersheds.shp"
    )
    closed_path = (
        paths.data_dir
        / "raw"
        / "hydro"
        / "watersheds"
        / "closed"
        / "watersheds.shp"
    )

    _watersheds: list[pl.DataFrame] = []
    for name, path, url in zip(
        ("open", "closed"),
        (open_path, closed_path),
        (open_watersheds_url, closed_watersheds_url),
        strict=True,
    ):
        if force and path.parent.exists():
            # a stale extraction must not shadow the fresh one: the rename
            # pass below globs the whole directory
            shutil.rmtree(path.parent)
        if not path.exists():
            with task(
                f"Downloading {name} watersheds...",
                f"Downloaded {name} watersheds.",
            ):
                path.parent.mkdir(exist_ok=True, parents=True)
                zip_path = path.parent / "watersheds.zip"
                with httpx.Client(timeout=120.0) as client:
                    resp = client.get(url)
                    resp.raise_for_status()
                    zip_path.write_bytes(resp.content)
                with zipfile.ZipFile(zip_path, "r") as f:
                    f.extractall(path.parent)
                zip_path.unlink()
                for _path in path.parent.glob("**/*"):
                    _path.rename(path.parent / f"watersheds{_path.suffix}")
                for _path in path.parent.glob("*"):
                    if _path.is_dir():
                        _path.rmdir()

        # every vertex goes through pyproj one geometry at a time, which
        # is seconds of silence per shapefile without a task around it
        with task(
            f"Reprojecting {name} watersheds...",
            f"Reprojected {name} watersheds.",
        ):
            shapes = gpd.read_file(path)
            watersheds_ = pl.DataFrame(
                {
                    column: shapes[column].to_list()
                    for column in shapes.columns
                    if column != "geometry"
                }
            ).with_columns(
                # .to_list(): polars needs pyarrow (not a dependency here)
                # to ingest a pandas series, but takes a plain list of
                # bytes as is
                pl.Series(
                    "geometry",
                    shapes.geometry.to_wkb().to_list(),
                    dtype=pl.Binary,
                )
            )
            if name == "closed":
                watersheds_ = (
                    watersheds_.rename({"tp": "id"})
                    .sort("Sup_Km", descending=True)
                    .group_by("id")
                    .first()
                )
            else:
                watersheds_ = (
                    watersheds_.rename({"Station": "id"})
                    .sort("Sup_Diffus", descending=True)
                    .group_by("id")
                    .first()
                )

            # open watersheds ship in EPSG:4269, closed in EPSG:32198;
            # both are reprojected to lat/lon so downstream code sees one
            # CRS
            from_crs = "EPSG:4269" if name == "open" else "EPSG:32198"
            transformer = pyproj.Transformer.from_crs(
                from_crs, "EPSG:4326", always_xy=True
            ).transform
            watersheds_ = watersheds_.with_columns(
                pl.col("geometry").map_elements(
                    lambda wkb: (
                        shapely.to_wkb(
                            shapely.ops.transform(
                                transformer, shapely.from_wkb(wkb)
                            )
                        )
                        if wkb
                        else None
                    ),
                    return_dtype=pl.Binary,
                )
            )

            _watersheds.append(watersheds_.select("id", "geometry"))

    return pl.concat(_watersheds)


class _NoDemCoverageError(RuntimeError):
    """Raised when the STAC search finds no DEM over a watershed.

    A dedicated type so the caller cannot mislabel an unrelated
    RuntimeError from the raster stack as missing coverage.
    """


def _get_dem_data(
    watersheds: pl.DataFrame, *, n_bands: int = 5, force: bool = False
) -> pl.DataFrame:
    if n_bands < 1:
        raise ValueError(f"n_bands must be >= 1, got {n_bands}")

    dem_dir = paths.data_dir / "raw" / "hydro" / "dem"
    dem_dir.mkdir(parents=True, exist_ok=True)

    rows = watersheds.select("id", "geometry").to_dicts()
    _bands: list[dict] = []
    with progress_task(
        "Reading DEMs...", "Read DEMs.", total=len(rows)
    ) as progress:
        for row in rows:
            id = row["id"]
            wkb = row["geometry"]
            path = dem_dir / f"{id}.tiff"

            if force or not path.exists():
                if wkb is None:
                    raise RuntimeError(f"No watershed geometry for {id}.")
                try:
                    _download_dem(wkb, path)
                except _NoDemCoverageError as exc:
                    raise RuntimeError(f"No DEM coverage for {id}.") from exc
                except Exception as exc:
                    raise RuntimeError(
                        f"Failed DEM for {id}: {type(exc).__name__}: {exc}"
                    ) from exc

            bands = _compute_dem_bands(path, n_bands)
            _bands.append({"id": id, "elevation_layers": bands})
            progress.increment()

    return pl.DataFrame(
        _bands,
        schema={"id": pl.String, "elevation_layers": pl.List(pl.Float64)},
    )


def _download_dem(wkb: bytes, path: Path) -> None:
    geom_4326 = shapely.from_wkb(wkb)
    minx, miny, maxx, maxy = geom_4326.bounds  # WGS84 lon/lat for STAC bbox

    hrefs = _find_dtm_hrefs([minx, miny, maxx, maxy])
    if not hrefs:
        raise _NoDemCoverageError()

    # Reproject the watershed polygon 4326 -> native COG CRS for clipping
    # (same idiom as _download_watersheds).
    to_native = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:3979", always_xy=True
    ).transform
    geom_native = shapely.ops.transform(to_native, geom_4326)
    bminx, bminy, bmaxx, bmaxy = geom_native.bounds

    # Lazy open + windowed read per COG, bounded to the watershed box first.
    arrays = []
    for href in hrefs:
        # COG is a single-band raster, so open_rasterio returns a DataArray.
        da = cast(xr.DataArray, rioxarray.open_rasterio(href, masked=True))
        da = da.rio.clip_box(bminx, bminy, bmaxx, bmaxy)  # native-CRS box
        arrays.append(da)

    da = arrays[0] if len(arrays) == 1 else merge_arrays(arrays)

    # Exact polygon mask (geometry already in the raster CRS).
    da = da.rio.clip([geom_native], "EPSG:3979", drop=True, all_touched=True)

    # staged so an interrupted raster write never passes as a cached DEM;
    # the .tiff suffix stays because to_raster derives the format from it
    staged = path.parent / f"{path.stem}.part.tiff"
    da.rio.to_raster(staged)  # materializes only the windowed range requests
    staged.replace(path)


def _compute_dem_bands(path: Path, n_bands: int) -> list[float]:
    """Band-median reference elevations (airGR/CemaNeige ZLayers): the
    elevation quantile of each equal-area slice. Pixels are ~equal-area in
    EPSG:3979, so a plain pixel quantile is already area-weighted; masked=True
    turns nodata into NaN, which quantile skips."""
    da = cast(xr.DataArray, rioxarray.open_rasterio(path, masked=True))
    probs = [(2 * i - 1) / (2 * n_bands) for i in range(1, n_bands + 1)]
    return da.quantile(probs).values.tolist()


def _find_dtm_hrefs(bbox: list[float]) -> list[str]:
    client = Client.open("https://datacube.services.geo.ca/stac/api/")
    search = client.search(collections=["mrdem-30"], bbox=bbox)
    return [
        item.assets["dtm"].href
        for item in search.items()
        if "dtm" in item.assets
    ]


def _fetch_station_streamflow(client: httpx.Client, id: str) -> pl.DataFrame:
    # streamflow is converted from the source's m³/s to mm/day using the
    # drainage area from the file header, matching the models' depth units
    resp = client.get(streamflow_url.format(id=id))
    resp.raise_for_status()
    resp.encoding = "latin-1"

    area_match = streamflow_area_regex.search(resp.text)
    if area_match is None:
        raise ValueError(f"No drainage area in header for station {id}")
    area = float(area_match.group(1).replace(",", "."))
    if area <= 0:
        raise ValueError(f"Invalid drainage area {area} for station {id}")

    _data: list[tuple[str, str, float | None]] = []
    for line in resp.text.split("\n"):
        match = streamflow_row_regex.match(line.strip())
        if match is not None:
            station, date, value = match.groups()
            _data.append((station, date, float(value) if value else None))
    if not _data:
        raise ValueError(f"No streamflow rows for station {id}")

    data = (
        pl.DataFrame(
            _data,
            schema={
                "id": pl.String,
                "datetime": pl.String,
                "streamflow": pl.Float64,
            },
            orient="row",
        )
        .with_columns(
            pl.col("datetime").str.strptime(pl.Date, "%Y/%m/%d"),
        )
        # m³/s → mm/day: × 86400 s/day ÷ (km² × 10⁶ m²) × 10³ mm/m
        .with_columns(pl.col("streamflow") * 86.4 / area)
    )
    # gap-fill onto a dense daily grid so missing days are explicit nulls
    dense = data.select(
        pl.date_range(
            pl.col("datetime").min(), pl.col("datetime").max()
        ).alias("datetime")
    ).with_columns(pl.lit(id).alias("id"))
    return dense.join(data, on=["id", "datetime"], how="left").select(
        "id", "datetime", "streamflow"
    )


def _write_ipc(data: pl.DataFrame, path: Path) -> None:
    """Staged write: a crash mid-write never leaves a partial product."""
    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.parent / f"{path.name}.part"
    data.write_ipc(staged, compression="zstd")
    staged.replace(path)
