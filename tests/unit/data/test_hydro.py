import pytest

import holmes.data.hydro as hydro
from holmes.data.archive import MissingDataError


class TestGetStationData:
    def test_reads_product(self, tmp_data_dir, stations_df):
        path = tmp_data_dir / "raw" / "hydro" / "station_data.ipc"
        path.parent.mkdir(parents=True)
        stations_df.write_ipc(path, compression="zstd")

        assert hydro.get_station_data().equals(stations_df)

    def test_missing_product_raises(self, tmp_data_dir):
        with pytest.raises(MissingDataError, match="holmes download"):
            hydro.get_station_data()


class TestGetStreamflowData:
    def test_reads_product(self, tmp_data_dir, streamflow_df):
        data = streamflow_df.filter(streamflow_df["id"] == "061004")
        path = tmp_data_dir / "raw" / "hydro" / "streamflow" / "061004.ipc"
        path.parent.mkdir(parents=True)
        data.write_ipc(path, compression="zstd")

        assert hydro.get_streamflow_data("061004").equals(data)

    def test_missing_product_raises(self, tmp_data_dir):
        with pytest.raises(MissingDataError, match="holmes download"):
            hydro.get_streamflow_data("061004")

    def test_unknown_station_raises(self, tmp_data_dir):
        with pytest.raises(ValueError, match="Unknown station 999"):
            hydro.get_streamflow_data("999")
