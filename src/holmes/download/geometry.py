"""Shared geometry helpers for the build layer.

The geopandas/exactextract boundary used by the weather and projection
builders. Copies of the private helpers in `holmes.data.weather`, which
stay in place until the final cleanup pass.
"""

import exactextract
import geopandas as gpd
import numpy as np
import numpy.typing as npt
import polars as pl
import xarray as xr

##########
# public #
##########


def to_geopandas(stations: pl.DataFrame) -> gpd.GeoDataFrame:
    """Watershed polygons (WKB geometry column) as a geopandas frame."""
    return gpd.GeoDataFrame(
        {"id": stations["id"].to_list()},
        geometry=gpd.GeoSeries.from_wkb(stations["geometry"].to_list()),
        crs="EPSG:4326",
    )


def compute_coverage_weights(
    polygons: gpd.GeoDataFrame, weather_grid: xr.Dataset
) -> dict[str, tuple[npt.NDArray[np.int64], npt.NDArray[np.float64]]]:
    """Per-watershed grid cell ids and coverage fractions."""
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


def calculate_masked_mean(
    values: npt.NDArray[np.float64],
    cells: npt.NDArray[np.int64],
    weights: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    """Coverage-weighted mean over the covered cells, ignoring NaNs."""
    covered = values[:, cells]
    mask = ~np.isnan(covered)
    denominator = np.where(mask, weights, 0.0).sum(axis=1)
    numerator = np.where(mask, covered * weights, 0.0).sum(axis=1)
    return np.where(
        denominator > 0,
        numerator / np.where(denominator == 0, 1.0, denominator),
        np.nan,
    )
