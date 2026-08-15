import polars as pl
import pytest

import holmes.data.projection as projection
from holmes.data.archive import MissingDataError


def write_products(tmp_data_dir, projection_df) -> None:
    directory = tmp_data_dir / "raw" / "projection"
    directory.mkdir(parents=True)
    for (id_,), data in projection_df.partition_by("id", as_dict=True).items():
        data.write_ipc(directory / f"{id_}.ipc", compression="zstd")


class TestHasProjectionData:
    def test_all_present(self, tmp_data_dir, stations_df, projection_df):
        write_products(tmp_data_dir, projection_df)

        assert projection.has_projection_data(stations_df)

    def test_one_missing(self, tmp_data_dir, stations_df, projection_df):
        write_products(tmp_data_dir, projection_df)
        (tmp_data_dir / "raw" / "projection" / "061020.ipc").unlink()

        assert not projection.has_projection_data(stations_df)


class TestReadProjectionData:
    def test_concats_and_sorts(self, tmp_data_dir, stations_df, projection_df):
        write_products(tmp_data_dir, projection_df)

        data = projection.read_projection_data(stations_df)

        assert data.equals(projection_df)

    def test_missing_product_raises(self, tmp_data_dir, stations_df):
        with pytest.raises(MissingDataError, match="holmes download"):
            projection.read_projection_data(stations_df)

    def test_no_stations_raises(self, tmp_data_dir, stations_df):
        with pytest.raises(ValueError, match="No stations"):
            projection.read_projection_data(
                stations_df.filter(pl.col("id") == "none")
            )
