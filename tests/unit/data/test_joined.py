import pytest

import holmes.data.joined as joined
from holmes.data.archive import MissingDataError


class TestReadJoinedData:
    def test_reads_grid_method_product(self, tmp_data_dir, joined_df):
        path = tmp_data_dir / "raw" / "data_ministry_grid.ipc"
        path.parent.mkdir(parents=True)
        joined_df.write_ipc(path, compression="zstd")

        data = joined.read_joined_data(method="ministry_grid")

        assert data.equals(joined_df)

    def test_nearest_stations_product_carries_n(self, tmp_data_dir, joined_df):
        path = tmp_data_dir / "raw" / "data_nearest_stations_4.ipc"
        path.parent.mkdir(parents=True)
        joined_df.write_ipc(path, compression="zstd")

        data = joined.read_joined_data(method="nearest_stations", n_stations=4)

        assert data.equals(joined_df)

    def test_missing_product_raises(self, tmp_data_dir):
        with pytest.raises(MissingDataError, match="holmes download"):
            joined.read_joined_data(method="era5")

    @pytest.mark.parametrize("n_stations", [0, 6])
    def test_invalid_n_stations_raises(self, tmp_data_dir, n_stations):
        with pytest.raises(ValueError, match="n_stations must be between"):
            joined.read_joined_data(
                method="nearest_stations", n_stations=n_stations
            )
