from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

import holmes.app
import holmes.cli as cli
import holmes.data.hydro
import holmes.data.projection
import holmes.data.weather
import holmes.experiment

runner = CliRunner()


@pytest.fixture
def download_world(monkeypatch, stations_df):
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        holmes.data.hydro,
        "get_station_data",
        AsyncMock(return_value=stations_df),
    )
    monkeypatch.setattr(
        holmes.data.weather,
        "read_weather_data",
        lambda stations, **kwargs: calls.setdefault("era5", kwargs),
    )
    monkeypatch.setattr(
        holmes.data.weather,
        "rebuild_stations_backfill",
        lambda: calls.setdefault("backfill", True),
    )
    monkeypatch.setattr(
        holmes.data.projection,
        "has_projection_data",
        lambda stations: calls.setdefault("has_projection", False) and False,
    )

    async def read_projection_data(stations, *, rebuild):
        calls["projection"] = rebuild

    monkeypatch.setattr(
        holmes.data.projection, "read_projection_data", read_projection_data
    )
    return calls


class TestInitCli:
    def test_registers_commands(self):
        result = runner.invoke(cli._init_cli(), ["--help"])
        assert result.exit_code == 0
        for command in ["run", "download", "experiment"]:
            assert command in result.output


class TestRun:
    def test_starts_the_server(self, monkeypatch):
        server = MagicMock()
        monkeypatch.setattr(holmes.app, "run_server", server)
        result = runner.invoke(cli._init_cli(), ["run"])
        assert result.exit_code == 0
        server.assert_called_once()

    def test_is_the_default_command(self, monkeypatch):
        server = MagicMock()
        monkeypatch.setattr(holmes.app, "run_server", server)
        result = runner.invoke(cli._init_cli(), [])
        assert result.exit_code == 0
        server.assert_called_once()


class TestDownload:
    def test_cold_cache_rebuilds_everything(self, download_world):
        result = runner.invoke(cli._init_cli(), ["download"])
        assert result.exit_code == 0
        assert download_world["era5"] == {"method": "era5", "rebuild": True}
        assert download_world["backfill"] is True
        assert download_world["projection"] is False

    def test_existing_files_are_kept(
        self, tmp_data_dir, monkeypatch, download_world, weather_df
    ):
        era5_path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        era5_path.parent.mkdir(parents=True)
        weather_df.write_ipc(era5_path)
        backfill_path = (
            tmp_data_dir / "raw" / holmes.data.weather.stations_backfill_file
        )
        backfill_path.touch()
        monkeypatch.setattr(
            holmes.data.projection,
            "has_projection_data",
            lambda stations: True,
        )
        result = runner.invoke(cli._init_cli(), ["download"])
        assert result.exit_code == 0
        assert result.output.count("Already have") == 3
        assert "era5" not in download_world
        assert "backfill" not in download_world
        assert "projection" not in download_world

    def test_force_rebuilds_despite_files(
        self, tmp_data_dir, monkeypatch, download_world, weather_df
    ):
        era5_path = tmp_data_dir / "raw" / "weather" / "era5.ipc"
        era5_path.parent.mkdir(parents=True)
        weather_df.write_ipc(era5_path)
        monkeypatch.setattr(
            holmes.data.projection,
            "has_projection_data",
            lambda stations: True,
        )
        result = runner.invoke(cli._init_cli(), ["download", "--force"])
        assert result.exit_code == 0
        assert download_world["era5"]["rebuild"] is True
        assert download_world["backfill"] is True
        assert download_world["projection"] is True


class TestExperiment:
    def test_runs_the_experiments(self, monkeypatch):
        run = AsyncMock()
        monkeypatch.setattr(holmes.experiment, "run_experiment", run)
        result = runner.invoke(cli._init_cli(), ["experiment"])
        assert result.exit_code == 0
        run.assert_awaited_once()


class TestRunCli:
    def test_invokes_the_app(self, monkeypatch):
        app = MagicMock()
        monkeypatch.setattr(cli, "_init_cli", lambda: app)
        cli.run_cli()
        app.assert_called_once()
