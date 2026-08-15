import geopandas as gpd
import numpy as np
import polars as pl
import pytest
import rioxarray  # noqa: F401  # registers the .rio accessor
import shapely
import xarray as xr

import holmes.download.geometry as geometry

crs = "EPSG:32198"


@pytest.fixture
def polygons(stations_df: pl.DataFrame) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "id": stations_df["id"].to_list(),
            "geometry": [
                shapely.from_wkb(wkb) for wkb in stations_df["geometry"]
            ],
        },
        crs="EPSG:4326",
    ).to_crs(crs)


def make_weather_grid(polygons: gpd.GeoDataFrame, days: int = 3) -> xr.Dataset:
    min_x, min_y, max_x, max_y = polygons.total_bounds
    xs = np.linspace(min_x - 5000, max_x + 5000, 6)
    ys = np.linspace(min_y - 5000, max_y + 5000, 6)
    time = np.array(
        [
            np.datetime64(f"2015-01-{day + 1:02d}T05:00", "ns")
            for day in range(days)
        ]
    )
    data = xr.Dataset(
        {
            "precipitation": (
                ("time", "y", "x"),
                np.full((days, 6, 6), 2.0),
            ),
            "temperature": (("time", "y", "x"), np.full((days, 6, 6), -3.0)),
        },
        coords={"time": time, "y": ys, "x": xs},
    )
    data = data.rio.set_spatial_dims(x_dim="x", y_dim="y")
    return data.rio.write_crs(crs)


class TestToGeopandas:
    def test_polygons_from_wkb(self, stations_df):
        frame = geometry.to_geopandas(stations_df)
        assert frame["id"].to_list() == stations_df["id"].to_list()
        assert frame.crs is not None
        assert frame.crs.to_string() == "EPSG:4326"
        for i, wkb in enumerate(stations_df["geometry"]):
            assert frame.geometry.iloc[i].equals(shapely.from_wkb(wkb))


class TestComputeCoverageWeights:
    def test_weights_cover_every_watershed(self, polygons):
        grid = make_weather_grid(polygons)
        weights = geometry.compute_coverage_weights(polygons, grid)
        assert sorted(weights) == sorted(polygons["id"])
        for cell_ids, coverage in weights.values():
            assert cell_ids.dtype == np.int64
            assert coverage.dtype == np.float64
            assert len(cell_ids) == len(coverage)
            assert (coverage > 0).all()
            # a constant field's coverage-weighted mean is the constant
            n_cells = grid.sizes["y"] * grid.sizes["x"]
            values = grid["precipitation"].values.reshape(-1, n_cells)
            means = geometry.calculate_masked_mean(values, cell_ids, coverage)
            assert means == pytest.approx([2.0] * grid.sizes["time"])


class TestCalculateMaskedMean:
    def test_masks_nan_and_empty_denominator(self):
        values = np.array(
            [
                [1.0, 3.0, 100.0],
                [np.nan, 3.0, 100.0],
                [np.nan, np.nan, 100.0],
            ]
        )
        cells = np.array([0, 1])
        weights = np.array([1.0, 1.0])
        means = geometry.calculate_masked_mean(values, cells, weights)
        assert means[0] == pytest.approx(2.0)
        assert means[1] == pytest.approx(3.0)
        assert np.isnan(means[2])
