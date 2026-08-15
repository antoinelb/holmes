from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from typer.testing import CliRunner

import holmes.app
import holmes.cli as cli
import holmes.download
import holmes.download.package
import holmes.experiment

runner = CliRunner()


@pytest.fixture
def no_download_extra(monkeypatch):
    monkeypatch.setattr(
        cli.importlib,
        "import_module",
        MagicMock(side_effect=ImportError("No module named 'xarray'")),
    )


class TestInitCli:
    def test_registers_commands(self):
        result = runner.invoke(cli._init_cli(), ["--help"])
        assert result.exit_code == 0
        for command in ["run", "download", "package", "experiment"]:
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
    def test_runs_the_orchestrator(self, monkeypatch):
        run = MagicMock()
        monkeypatch.setattr(holmes.download, "run_download", run)
        result = runner.invoke(cli._init_cli(), ["download"])
        assert result.exit_code == 0
        run.assert_called_once_with(force=False)

    def test_force_is_passed_through(self, monkeypatch):
        run = MagicMock()
        monkeypatch.setattr(holmes.download, "run_download", run)
        result = runner.invoke(cli._init_cli(), ["download", "--force"])
        assert result.exit_code == 0
        run.assert_called_once_with(force=True)

    def test_missing_extra_fails_with_hint(self, no_download_extra):
        result = runner.invoke(cli._init_cli(), ["download"])
        assert result.exit_code == 1
        assert "holmes-hydro[download]" in result.output


class TestPackage:
    def test_builds_the_archive(self, monkeypatch):
        build = MagicMock()
        monkeypatch.setattr(holmes.download.package, "build_archive", build)
        result = runner.invoke(cli._init_cli(), ["package"])
        assert result.exit_code == 0
        build.assert_called_once_with(None)

    def test_output_is_passed_through(self, monkeypatch, tmp_path):
        build = MagicMock()
        monkeypatch.setattr(holmes.download.package, "build_archive", build)
        output = tmp_path / "data.zip"
        result = runner.invoke(
            cli._init_cli(), ["package", "--output", str(output)]
        )
        assert result.exit_code == 0
        build.assert_called_once_with(Path(output))

    def test_missing_extra_fails_with_hint(self, no_download_extra):
        result = runner.invoke(cli._init_cli(), ["package"])
        assert result.exit_code == 1
        assert "holmes-hydro[download]" in result.output


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
