import asyncio
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable, Literal, NamedTuple, assert_never

import cf_xarray
import geopandas as gpd
import httpx
import numpy as np
import numpy.typing as npt
import polars as pl
import pyproj
import rasterio
import rasterio.mask
import tqdm
import xarray as xr

#########
# types #
#########

data_dir = Path(__file__).parent / ".." / "data" / "hydro"


class Metadata(NamedTuple):
    id: str
    name: str
    lat: float
    lon: float
    area: float
    elevation_bands: npt.NDArray[np.float64]
    median_elevation: float
    watershed: gpd.GeoDataFrame


########
# main #
########


def main() -> None:
    # 061028 to test open, 061023 to test closed
    station_id = _parse_args()
    if station_id is None:
        sys.exit(2)
        return  # to make type checkers happy

    path = data_dir / "stations" / f"{station_id}.nc"
    path.parent.mkdir(exist_ok=True, parents=True)

    if path.exists():
        done_print(f"{station_id} dataset already exists.")
        load_print(f"Testing {station_id} read...")
        dataset = xr.open_dataset(path)
        gpd.GeoDataFrame(
            geometry=cf_xarray.geometry.cf_to_shapely(dataset).values,
            crs=pyproj.CRS.from_cf(dataset["crs"].attrs),
        )
        done_print(f"{station_id} read worked.")
    else:
        metadata = asyncio.run(read_metadata(station_id))
        data = asyncio.run(read_data(station_id))
        dataset = combine_data_and_metadata(data, metadata)
        load_print(f"Writing {station_id} dataset to netcdf...")
        dataset.to_netcdf(path)
        done_print(f"Wrote {station_id} dataset to netcdf.")


async def read_metadata(station_id: str, *, echo: bool = True):
    path = data_dir / "stations" / f"{station_id}.json"
    watershed_path = data_dir / "stations" / f"{station_id}.gpkg"
    if path.exists() and watershed_path.exists():
        load_print(
            f"Reading cached metadata for station id {station_id}...",
            echo=echo,
        )
        watershed = gpd.read_file(watershed_path)
        with open(path, "r") as f:
            _metadata = json.load(f)
            metadata = Metadata(
                id=_metadata["id"],
                name=_metadata["name"],
                lat=_metadata["lat"],
                lon=_metadata["lon"],
                area=_metadata["area"],
                elevation_bands=np.array(_metadata["elevation_bands"]),
                median_elevation=_metadata["median_elevation"],
                watershed=watershed,
            )
        done_print(
            f"Read cached metadata for station id {station_id}.",
            echo=echo,
        )
        return metadata
    else:
        load_print(
            f"Reading metadata for station id {station_id}...",
            echo=echo,
        )
        stations = _read_stations(echo=echo, echo_indent=2)
        station = stations.filter(pl.col("id") == station_id)
        if station.shape[0] == 0:
            raise ValueError(f"Station with id {station_id} doesn't exist.")
        watershed, elevation_bands, median_elevation = (
            await _get_watershed_data(
                station_id, open=station[0, "open"], echo=echo, echo_indent=2
            )
        )
        metadata = Metadata(
            id=station_id,
            name=station[0, "name"],
            lat=station[0, "lat"],
            lon=station[0, "lon"],
            area=station[0, "area"],
            elevation_bands=np.array(elevation_bands),
            median_elevation=median_elevation,
            watershed=watershed,
        )
        load_print(
            f"Writing cached metadata for station id {station_id}...",
            echo=echo,
        )
        with open(path, "w") as f:
            metadata_dict = metadata._asdict()
            del metadata_dict["watershed"]
            metadata_dict["elevation_bands"] = (
                metadata.elevation_bands.tolist()
            )
            json.dump(metadata_dict, f, indent=2)
        watershed.to_file(watershed_path, driver="GPKG")
        done_print(
            f"Read metadata for station id {station_id}.",
            echo=echo,
        )
        return metadata


async def read_data(station_id: str, *, echo: bool = True) -> pl.DataFrame:
    path = data_dir / "stations" / f"{station_id}.ipc"

    if path.exists():
        load_print(
            f"Reading cached data for station id {station_id}...",
            echo=echo,
        )
        data = pl.read_ipc(path)
        done_print(
            f"Read cached data for station id {station_id}.",
            echo=echo,
        )
        return data
    else:
        load_print(
            f"Downloading data for station id {station_id}...",
            echo=echo,
        )
        data = await _fetch_data(station_id)
        load_print(
            f"Writing cached data for station id {station_id}...",
            echo=echo,
        )
        path.parent.mkdir(exist_ok=True, parents=True)
        data.write_ipc(path)
        done_print(
            f"Read data for station id {station_id}.",
            echo=echo,
        )
        return data


def combine_data_and_metadata(
    data: pl.DataFrame, metadata: Metadata, *, echo: bool = True
) -> xr.Dataset:
    load_print(
        f"Combining {metadata.id} data and metadata to xarray...", echo=echo
    )
    dataset = xr.Dataset(
        data_vars={
            "streamflow": ("date", data["streamflow"].to_numpy()),
            "elevation_bands": ("band", metadata.elevation_bands),
        },
        coords={
            "date": data["date"].to_numpy(),
            "band": np.arange(len(metadata.elevation_bands)),
        },
        attrs={
            "station_id": metadata.id,
            "station_name": metadata.name,
            "area_km2": metadata.area,
            "median_elevation_m": metadata.median_elevation,
        },
    )
    geometry_dataset = cf_xarray.geometry.shapely_to_cf(
        list(metadata.watershed.geometry)
    )
    dataset = xr.merge([dataset, geometry_dataset])
    dataset["crs"] = xr.DataArray(0, attrs=metadata.watershed.crs.to_cf())
    for var in ["x", "y", "crd_x", "crd_y"]:
        dataset[var].attrs["grid_mapping"] = "crs"

    done_print(
        f"Combined {metadata.id} data and metadata to xarray.", echo=echo
    )
    return dataset


def _parse_args() -> str | None:
    if len(sys.argv) == 2 and sys.argv[1] not in ("--help", "-h"):
        station_id = sys.argv[1]
        return station_id
    else:
        print("Usage: python download_hydro_data <station_id>")
        print()
        print(
            "Downloads the hydrological data for the given station id. "
            + "You can find this id in the Atlas hydroclimatique du Québec "
            + "(https://www.cehq.gouv.qc.ca/atlas-hydroclimatique/stations-hydrometriques/index.htm)."
        )
        print()
        print("Positional arguments:")
        print("  station_id  The hydrological station id")
        return None


############
# metadata #
############


def _read_stations(*, echo: bool = True, echo_indent: int = 0) -> pl.DataFrame:
    url = "https://www.donneesquebec.ca/recherche/dataset/c31e2bee-a899-46ca-ad84-5798f0f49676/resource/6b2d32ef-80e2-445b-9bd1-97ddc39b5d59/download/stations_hydrometriques.csv"
    path = data_dir / "stations.ipc"
    if path.exists():
        load_print("Reading cached stations...", echo=echo, indent=echo_indent)
        stations = pl.read_ipc(path)
        done_print("Read cached stations.", echo=echo, indent=echo_indent)
    else:
        load_print("Downloading stations...", echo=echo, indent=echo_indent)
        stations = (
            pl.read_csv(url, schema_overrides={"no": pl.String})
            .select(
                pl.col("no").alias("id"),
                pl.col("nom").alias("name"),
                "type",
                pl.col("latitude").alias("lat"),
                pl.col("longitude").alias("lon"),
                pl.col("debut").cast(pl.Int64, strict=False).alias("start"),
                pl.col("fin").cast(pl.Int64, strict=False).alias("end"),
                pl.col("cours_eau").alias("waterway"),
                pl.col("superficie").alias("area"),
                (pl.col("regime") == "Influencé").alias("influenced"),
                (pl.col("etat") == "Ouverte").alias("open"),
                (pl.col("lien_historique") == "www.eau.ec.gc.ca").alias(
                    "federal"
                ),
            )
            .filter(pl.col("type").str.contains("Débit") & ~pl.col("federal"))
            .drop("type", "federal")
        )
        load_print("Writing cached stations...", echo=echo, indent=echo_indent)
        path.parent.mkdir(parents=True, exist_ok=True)
        stations.write_ipc(path)
        done_print("Read stations.", echo=echo, indent=echo_indent)
    return stations


async def _get_watershed_data(
    station_id: str, *, open: bool, echo: bool = True, echo_indent: int = 0
) -> tuple[gpd.GeoDataFrame, list[float], float]:
    watersheds = await _get_watersheds(
        open=open, echo=echo, echo_indent=echo_indent
    )
    if "tp" in watersheds.columns:
        watershed = watersheds[watersheds["tp"] == station_id]
    elif "Station" in watersheds.columns:
        watershed = watersheds[watersheds["Station"] == station_id]
    else:
        raise RuntimeError(
            'Either the "Station" or "tp" columns must be present '
            "in the dataframe."
        )
    if watershed.shape[0] == 2:
        watershed = watershed[watershed["Type"] == "J"]
    if watershed.shape[0] == 0:
        raise ValueError(
            f"Watershed for station with id {station_id} doesn't exist."
        )

    watershed = watershed.reset_index()

    elevation_bands, median_elevation = await _get_watershed_elevation_bands(
        station_id, watershed, echo=echo, echo_indent=echo_indent
    )

    return watershed, elevation_bands, median_elevation


async def _get_watersheds(
    *, open: bool, echo: bool = True, echo_indent: int = 0
) -> gpd.GeoDataFrame:
    if open:
        url = (
            "https://www.donneesquebec.ca/recherche/dataset/"
            "c31e2bee-a899-46ca-ad84-5798f0f49676/resource/"
            "924cce0a-5fcc-47fa-a725-5ec84522090f/download/"
            "bassins_versants_stations_ouvertes.zip"
        )
        path = data_dir / "watersheds_open" / "watersheds.shp"
    else:
        url = (
            "https://www.donneesquebec.ca/recherche/dataset/"
            "c31e2bee-a899-46ca-ad84-5798f0f49676/resource/"
            "8020bb47-8124-4cc2-a5ad-e2c312e7c7cf/"
            "download/bv_stations_fermees.zip"
        )
        path = data_dir / "watersheds_closed" / "watersheds.shp"
    if path.exists():
        load_print(
            "Reading watersheds shapefile...", echo=echo, indent=echo_indent
        )
        watersheds = gpd.read_file(path)
        done_print("Read watersheds shapefile.", echo=echo, indent=echo_indent)
        return watersheds
    else:
        load_print(
            "Downloading watersheds shapefile...",
            echo=echo,
            indent=echo_indent,
        )
        path.parent.mkdir(exist_ok=True, parents=True)
        zip_path = path.parent / "watersheds.zip"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
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
        load_print(
            "Reading watersheds shapefile...", echo=echo, indent=echo_indent
        )
        watersheds = gpd.read_file(path.parent / "watersheds.shp")
        done_print("Read watersheds shapefile.", echo=echo, indent=echo_indent)
        return watersheds


async def _get_watershed_elevation_bands(
    station_id: str,
    watershed: gpd.GeoDataFrame,
    *,
    n_bands: int = 5,
    resolution: float = 25,
    echo: bool = True,
    echo_indent: int = 0,
) -> tuple[list[float], float]:
    dem_path = await _get_dem_path(
        station_id,
        watershed,
        resolution=resolution,
        echo=echo,
        echo_indent=echo_indent,
    )

    load_print("Extracting elevation bands...", echo=echo, indent=echo_indent)
    with rasterio.open(dem_path) as src:
        watershed = watershed.to_crs(src.crs)

        out_image, out_transform = rasterio.mask.mask(
            src, watershed.geometry, crop=True
        )
        elevations = out_image[0]

        # Get valid (non-nodata) values
        nodata = src.nodata if src.nodata else -9999
        valid_mask = (elevations != nodata) & np.isfinite(elevations)
        elevations = elevations[valid_mask]
        if len(elevations) == 0:
            raise ValueError("No valid elevation data within watershed.")

        edges = np.linspace(
            np.min(elevations), np.max(elevations), n_bands + 1
        )

        bands = []
        for i in range(n_bands):
            band_min = edges[i]
            band_max = edges[i + 1]

            # Count pixels in this band
            if i == n_bands - 1:
                in_band = (elevations >= band_min) & (elevations <= band_max)
            else:
                in_band = (elevations >= band_min) & (elevations < band_max)

            band_elevs = elevations[in_band]
            median_elev = (
                float(np.median(band_elevs))
                if len(band_elevs) > 0
                else (band_min + band_max) / 2
            )

            bands.append(median_elev)
    median_elevation = float(np.median(np.array(bands)))
    done_print("Extracted elevation bands.", echo=echo, indent=echo_indent)
    return bands, median_elevation


async def _get_dem_path(
    station_id: str,
    watershed: gpd.GeoDataFrame,
    *,
    resolution: float = 25,
    echo: bool = True,
    echo_indent: int = 0,
) -> Path:
    path = data_dir / "dem" / f"{station_id}.tiff"

    if path.exists():
        return path
    else:
        load_print("Downloading dem file...", echo=echo, indent=echo_indent)
        path.parent.mkdir(exist_ok=True, parents=True)
        watershed = watershed.to_crs("EPSG:4326")
        min_lon, min_lat, max_lon, max_lat = watershed.total_bounds
        res_deg = resolution / 111000  # approximate degrees per meter
        url = (
            "https://datacube.services.geo.ca/wrapper/ogc/elevation-hrdem-mosaic"
            "?SERVICE=WCS"
            "&VERSION=1.1.1"
            "&REQUEST=GetCoverage"
            "&IDENTIFIER=dtm"
            "&FORMAT=image/geotiff"
            f"&BOUNDINGBOX={min_lat},{min_lon},{max_lat},{max_lon},urn:ogc:def:crs:EPSG::4326"
            f"&GRIDBASECRS=urn:ogc:def:crs:EPSG::4326"
            f"&GRIDOFFSETS={-res_deg},{res_deg}"
        )
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.get(url)
            try:
                resp.raise_for_status()
            except Exception:
                print(resp.text)
                raise
            path.write_bytes(resp.content)
        done_print("Downloaded dem file.", echo=echo, indent=echo_indent)
        return path


########
# data #
########


async def _fetch_data(station_id: str) -> pl.DataFrame:
    base_url = "https://www.cehq.gouv.qc.ca/depot/historique_donnees/fichier"
    async with httpx.AsyncClient() as client:
        datasets = await asyncio.gather(
            _fetch_dataset(client, base_url, station_id, "streamflow"),
            _fetch_dataset(client, base_url, station_id, "level"),
        )
    if datasets[0] is None:
        raise FileNotFoundError(
            f"There is not streamflow data for station {station_id}."
        )
    if datasets[1] is None:
        data = datasets[0]
    else:
        data = datasets[0].join(datasets[1], on=["date", "lat", "lon"])
        if data["date"].n_unique() != data.shape[0]:
            raise RuntimeError(
                "There was an error joining the streamflow and level data."
            )
    return data


async def _fetch_dataset(
    client: httpx.AsyncClient,
    base_url: str,
    id: str,
    type: Literal["streamflow", "level"],
) -> pl.DataFrame | None:
    match type:
        case "streamflow":
            url = f"{base_url}/{id}_Q.txt"
        case "level":
            url = f"{base_url}/{id}_N.txt"
        case _:
            assert_never(type)

    resp = await client.get(url)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    resp.encoding = "latin-1"

    _data: list[list[str]] = []
    reading = False
    lat = None
    lon = None
    area = None

    for line in resp.text.split("\n"):
        if line.startswith("Coordonnées:"):
            match = re.match(
                r"^Coordonnées:\s+\([^)]+\) (-?\d+)° (\d+)' (\d+)\" // (-?\d+)° (\d+)' (\d+)\"$",
                line.strip(),
            )
            if match is None:
                raise RuntimeError(
                    "There was an error reading the coordinates."
                )
            lat = _convert_lat_lon_to_decimal(
                float(match.group(1)),
                float(match.group(2)),
                float(match.group(3)),
            )
            lon = _convert_lat_lon_to_decimal(
                float(match.group(4)),
                float(match.group(5)),
                float(match.group(6)),
            )
        if line.startswith("Bassin versant:"):
            area = float(line.split()[2])
        elif line.startswith("Station") and not line.startswith("Station:"):
            reading = True
        elif reading:
            _data.append(line.strip().split())

    if lat is None or lon is None:
        raise RuntimeError("There was an error reading the coordinates.")

    return pl.DataFrame(
        [[line[1], line[2]] for line in _data if len(line) > 2],
        schema={"date": pl.String, type: pl.Float64},
        orient="row",
    ).with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y/%m/%d"),
        pl.lit(lat).alias("lat"),
        pl.lit(lon).alias("lon"),
        pl.lit(area).alias("area"),
    )


def _convert_lat_lon_to_decimal(
    hours: float, minutes: float, seconds: float
) -> float:
    return hours + minutes / 60 + seconds / 3600


#########
# utils #
#########


def load_print(
    text: str,
    symbol: str = "*",
    indent: int = 0,
    echo: bool = True,
    end: str = "\r",
) -> None:
    symbol = f"\033[1m[{symbol}]\033[0m"
    if echo:
        print(
            f"\r{' ' * indent}{symbol} {text}".ljust(
                shutil.get_terminal_size().columns
            ),
            end=end,
        )


def done_print(
    text: str,
    symbol: str = "+",
    indent: int = 0,
    echo: bool = True,
    overwrite_n_extra_lines: int = 0,
) -> None:
    symbol = f"\033[1m\033[92m[{symbol}]\033[0m"
    if echo:
        if overwrite_n_extra_lines:
            cursor_up(overwrite_n_extra_lines + 1)
            for _ in range(overwrite_n_extra_lines):
                print(" ".ljust(shutil.get_terminal_size().columns))
            cursor_up(overwrite_n_extra_lines + 1)
        print(
            f"\r{' ' * indent}{symbol} {text}".ljust(
                shutil.get_terminal_size().columns
            )
        )


def load_progress(
    iter_: Iterable[Any],
    text: str,
    symbol: str = "*",
    indent: int = 0,
    echo: bool = True,
    *args: Any,
    **kwargs: Any,
) -> Iterable[Any]:
    if echo:
        return tqdm.tqdm(
            iter_,
            f"{' ' * indent}[{symbol}] {text}",
            *args,
            leave=False,
            position=0,
            file=sys.stdout,
            **kwargs,
        )
    else:
        return iter_


def cursor_up(n: int) -> None:
    print(f"\x1b[{n}A")


if __name__ == "__main__":
    main()
