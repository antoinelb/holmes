import asyncio
import re
import zipfile
from pathlib import Path
from typing import cast

import geopolars as gpl
import httpx
import polars as pl
import pyproj
import rioxarray
import shapely
import shapely.ops
import xarray as xr
from pystac_client import Client
from rioxarray.merge import merge_arrays

from holmes.utils.paths import data_dir
from holmes.utils.print import done_print, load_print

#########
# types #
#########

STATIONS = [
    "061004",
    "061020",
    "061021",
    "061022",
    "061023",
    "061024",
    "061028",
    "061029",
]

##########
# public #
##########


async def get_station_data(
    *, echo: bool = True, indent: int = 0
) -> pl.DataFrame:
    path = data_dir / "raw" / "hydro" / "station_data.ipc"
    if path.exists():
        load_print("Reading cached station data...", echo=echo, indent=indent)
        data = pl.read_ipc(path)
        done_print("Read cached station data.", echo=echo, indent=indent)
        return data
    else:
        stations = _get_stations()
        stations = _rename_stations(stations)
        watersheds = await _get_watersheds(stations)
        data = stations.join(watersheds, on="id", how="left")
        load_print("Writing cached station data...", echo=echo, indent=indent)
        data.write_ipc(path)
        done_print("Read station data.", echo=echo, indent=indent)
        return data


async def get_streamflow_data(id: str) -> pl.DataFrame:
    path = data_dir / "raw" / "hydro" / "streamflow" / f"{id}.ipc"

    if path.exists():
        return pl.read_ipc(path)

    async with httpx.AsyncClient() as client:
        data = await _get_streamflow_data(client, id)
    # gap-fill onto a dense daily grid so missing days are explicit nulls
    dense = data.select(
        pl.date_range(
            pl.col("datetime").min(), pl.col("datetime").max()
        ).alias("datetime")
    ).with_columns(pl.lit(id).alias("id"))
    data = dense.join(data, on=["id", "datetime"], how="left").select(
        "id", "datetime", "streamflow"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    data.write_ipc(path)
    return data


###########
# private #
###########


def _get_stations() -> pl.DataFrame:
    url = "https://www.donneesquebec.ca/recherche/dataset/c31e2bee-a899-46ca-ad84-5798f0f49676/resource/6b2d32ef-80e2-445b-9bd1-97ddc39b5d59/download/stations_hydrometriques.csv"
    path = data_dir / "raw" / "hydro" / "stations.ipc"
    if path.exists():
        load_print("Reading cached stations...")
        stations = pl.read_ipc(path)
        done_print("Read cached stations.")
    else:
        load_print("Downloading stations...")
        stations = pl.read_csv(url, schema_overrides={"no": pl.String}).select(
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
        load_print("Writing cached stations...")
        path.parent.mkdir(parents=True, exist_ok=True)
        stations.write_ipc(path)
        done_print("Read stations.")
    return stations


def _rename_stations(stations: pl.DataFrame) -> pl.DataFrame:
    return stations.with_columns(
        pl.when(pl.col("id") == "061028")
        .then(pl.lit("Pikauba Aval"))
        .when(pl.col("id") == "061022")
        .then(pl.lit("Pikauba Amont"))
        .otherwise(pl.col("name"))
        .alias("name")
    )


async def _get_watersheds(stations: pl.DataFrame) -> pl.DataFrame:
    path = data_dir / "raw" / "hydro" / "watersheds" / "watersheds.ipc"
    if path.exists():
        load_print("Reading cached watersheds...")
        data = pl.read_ipc(path)
        done_print("Read cached watersheds.")
        return data
    else:
        watersheds = await _download_watersheds()
        load_print("Writing cached watersheds...")
        data = stations.select("id").join(watersheds, on="id", how="left")
        data = data.with_columns(
            pl.col("geometry")
            .map_elements(
                lambda wkb: (
                    shapely.to_geojson(shapely.from_wkb(wkb))
                    if wkb is not None
                    else None
                ),
                return_dtype=pl.String,
            )
            .alias("geometry_geojson"),
        )
        dem = await _get_dem_data(data)
        data = data.join(dem, on="id", how="left")
        data.write_ipc(path)
        done_print("Read watersheds.")
        return data


async def _download_watersheds() -> pl.DataFrame:
    open_url = "https://www.donneesquebec.ca/recherche/dataset/c31e2bee-a899-46ca-ad84-5798f0f49676/resource/924cce0a-5fcc-47fa-a725-5ec84522090f/download/bassins_versants_stations_ouvertes.zip"
    closed_url = (
        "https://www.donneesquebec.ca/recherche/dataset/"
        "c31e2bee-a899-46ca-ad84-5798f0f49676/resource/"
        "8020bb47-8124-4cc2-a5ad-e2c312e7c7cf/"
        "download/bv_stations_fermees.zip"
    )
    open_path = (
        data_dir / "raw" / "hydro" / "watersheds" / "open" / "watersheds.shp"
    )
    closed_path = (
        data_dir / "raw" / "hydro" / "watersheds" / "closed" / "watersheds.shp"
    )

    _watersheds: list[pl.DataFrame] = []
    for name, path, url in zip(
        ("open", "closed"),
        (open_path, closed_path),
        (open_url, closed_url),
        strict=True,
    ):
        if not path.exists():
            load_print(f"Downloading {name} watersheds zip file...")
            path.parent.mkdir(exist_ok=True, parents=True)
            zip_path = path.parent / "watersheds.zip"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url)
                resp.raise_for_status()
                zip_path.write_bytes(resp.content)
            load_print(f"Extracting {name} watersheds zip file...")
            with zipfile.ZipFile(zip_path, "r") as f:
                f.extractall(path.parent)
            zip_path.unlink()
            for _path in path.parent.glob("**/*"):
                _path.rename(path.parent / f"watersheds{_path.suffix}")
            for _path in path.parent.glob("*"):
                if _path.is_dir():
                    _path.rmdir()

        load_print(f"Reading {name} watersheds...")
        watersheds_ = gpl.read_file(path)
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
        done_print(f"Read cached {name} watersheds.")

    watersheds = pl.concat(_watersheds)

    return watersheds


async def _get_dem_data(
    watersheds: pl.DataFrame,
    *,
    n_bands: int = 5,
    echo: bool = True,
    indent: int = 0,
) -> pl.DataFrame:
    if n_bands < 1:
        raise ValueError(f"n_bands must be >= 1, got {n_bands}")

    dem_dir = data_dir / "raw" / "hydro" / "dem"
    dem_dir.mkdir(parents=True, exist_ok=True)

    n = len(watersheds)
    _bands: list[dict] = []
    for i, row in enumerate(watersheds.select("id", "geometry").to_dicts()):
        id = row["id"]
        wkb = row["geometry"]
        path = dem_dir / f"{id}.tiff"
        symbol = f"{i + 1}/{n}"

        if not path.exists():
            if wkb is None:
                raise RuntimeError(
                    f"No watershed geometry for {id}; skipping DEM."
                )

            load_print(
                f"Downloading DEM for {id}...",
                symbol=symbol,
                indent=indent,
                echo=echo,
            )
            try:
                await asyncio.to_thread(_download_dem, wkb, path)
            except RuntimeError as exc:
                raise RuntimeError(
                    f"No DEM coverage for {id}; skipping."
                ) from exc
            except Exception as exc:
                raise RuntimeError(
                    f"Failed DEM for {id}: {type(exc).__name__}: {exc}"
                ) from exc

        load_print(
            f"Reading DEM bands for {id}...",
            symbol=symbol,
            indent=indent,
            echo=echo,
        )
        bands = await asyncio.to_thread(_compute_dem_bands, path, n_bands)
        _bands.append({"id": id, "elevation_layers": bands})
    done_print("Read DEM for stations.", indent=indent, echo=echo)

    bands_df = pl.DataFrame(
        _bands,
        schema={"id": pl.String, "elevation_layers": pl.List(pl.Float64)},
    )
    return bands_df


def _download_dem(wkb: bytes, path: Path) -> None:
    geom_4326 = shapely.from_wkb(wkb)
    minx, miny, maxx, maxy = geom_4326.bounds  # WGS84 lon/lat for STAC bbox

    hrefs = _find_dtm_hrefs([minx, miny, maxx, maxy])
    if not hrefs:
        raise RuntimeError()

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

    da.rio.to_raster(path)  # materializes only the windowed range requests


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


async def _get_streamflow_data(
    client: httpx.AsyncClient, id: str
) -> pl.DataFrame:
    # streamflow is converted from the source's m³/s to mm/day using the
    # drainage area from the file header, matching the models' depth units
    url = f"https://www.cehq.gouv.qc.ca/depot/historique_donnees/fichier/{id}_Q.txt"
    row_regex = re.compile(
        r"(\d+)\s+(\d{4}/\d{2}/\d{2})(?:\s+(-?\d+(?:\.\d+)?))?"
    )
    area_regex = re.compile(r"Bassin versant:\s*([\d.,]+)\s*km")

    resp = await client.get(url)
    resp.raise_for_status()
    resp.encoding = "latin-1"

    area_match = area_regex.search(resp.text)
    if area_match is None:
        raise ValueError(f"No drainage area in header for station {id}")
    area = float(area_match.group(1).replace(",", "."))
    if area <= 0:
        raise ValueError(f"Invalid drainage area {area} for station {id}")

    _data: list[tuple[str, str, float | None]] = []

    for line in resp.text.split("\n"):
        match = row_regex.match(line.strip())
        if match is not None:
            station, date, value = match.groups()
            _data.append((station, date, float(value) if value else None))
    return (
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
