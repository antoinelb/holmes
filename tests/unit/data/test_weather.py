import pytest

import holmes.data.weather as weather
from holmes.data.archive import MissingDataError


class TestReadWeatherData:
    def test_reads_grid_method_product(self, tmp_data_dir, weather_df):
        path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        path.parent.mkdir(parents=True)
        weather_df.write_ipc(path, compression="zstd")

        assert weather.read_weather_data(method="era5").equals(weather_df)

    def test_nearest_stations_product_carries_n(
        self, tmp_data_dir, weather_df
    ):
        path = tmp_data_dir / "raw" / "weather" / "nearest_stations_4.ipc"
        path.parent.mkdir(parents=True)
        weather_df.write_ipc(path, compression="zstd")

        data = weather.read_weather_data(
            method="nearest_stations", n_stations=4
        )

        assert data.equals(weather_df)

    def test_missing_product_raises(self, tmp_data_dir):
        with pytest.raises(MissingDataError, match="holmes download"):
            weather.read_weather_data(method="ministry_grid")

    @pytest.mark.parametrize("n_stations", [0, 6])
    def test_invalid_n_stations_raises(self, tmp_data_dir, n_stations):
        with pytest.raises(ValueError, match="n_stations must be between"):
            weather.read_weather_data(
                method="nearest_stations", n_stations=n_stations
            )


class TestReadWeatherGrid:
    def test_reads_product(self, tmp_data_dir, grid_df):
        path = tmp_data_dir / "raw" / "weather" / "grid_nearest_stations.ipc"
        path.parent.mkdir(parents=True)
        grid_df.write_ipc(path, compression="zstd")

        data = weather.read_weather_grid(method="nearest_stations")

        assert data.equals(grid_df)

    def test_missing_product_raises(self, tmp_data_dir):
        with pytest.raises(MissingDataError, match="holmes download"):
            weather.read_weather_grid(method="era5")
