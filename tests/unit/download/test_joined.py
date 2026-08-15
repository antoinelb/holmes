from pathlib import Path

import polars as pl
import pytest
from polars.testing import assert_frame_equal

import holmes.download.joined as joined
from holmes.data.archive import MissingDataError

product_names = [
    "era5",
    "ministry_grid",
    *(f"nearest_stations_{n}" for n in range(1, 6)),
]


@pytest.fixture
def streamflow_files(tmp_data_dir: Path, streamflow_df: pl.DataFrame) -> None:
    directory = tmp_data_dir / "raw" / "hydro" / "streamflow"
    directory.mkdir(parents=True)
    for (id_,), data in streamflow_df.partition_by("id", as_dict=True).items():
        data.write_ipc(directory / f"{id_}.ipc", compression="zstd")


@pytest.fixture
def weather_products(tmp_data_dir: Path, weather_df: pl.DataFrame) -> None:
    directory = tmp_data_dir / "raw" / "weather"
    directory.mkdir(parents=True)
    for name in product_names:
        weather_df.write_ipc(directory / f"{name}.ipc", compression="zstd")


class TestBuildJoinedData:
    def test_builds_all_seven_products(
        self,
        tmp_data_dir,
        stations_df,
        streamflow_files,
        weather_products,
        joined_df,
    ):
        joined.build_joined_data(stations_df)

        for name in product_names:
            path = tmp_data_dir / "raw" / f"data_{name}.ipc"
            assert path.exists()
            assert not path.with_suffix(".part").exists()

        # every product must carry the exact frame read_data would build
        assert_frame_equal(
            pl.read_ipc(
                tmp_data_dir / "raw" / "data_era5.ipc", memory_map=False
            ),
            joined_df,
        )

    def test_missing_streamflow_names_the_file(
        self, stations_df, weather_products
    ):
        with pytest.raises(MissingDataError, match=r"streamflow/061004\.ipc"):
            joined.build_joined_data(stations_df)

    def test_missing_weather_product_names_the_file(
        self, stations_df, streamflow_files
    ):
        with pytest.raises(MissingDataError, match=r"weather/era5\.ipc"):
            joined.build_joined_data(stations_df)

    def test_rejects_empty_stations(self):
        with pytest.raises(ValueError):
            joined.build_joined_data(pl.DataFrame(schema={"id": pl.String}))

    def test_rejects_stations_without_ids(self):
        with pytest.raises(ValueError):
            joined.build_joined_data(pl.DataFrame({"name": ["Station"]}))
