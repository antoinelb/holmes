from unittest.mock import MagicMock

import pytest
from starlette.applications import Starlette

import holmes.app as app
from holmes.data.archive import MissingDataError


@pytest.fixture
def no_sync(monkeypatch):
    sync = MagicMock()
    monkeypatch.setattr(app.archive, "sync_data", sync)
    return sync


class TestCreateApp:
    def test_builds_starlette_app(self, monkeypatch, no_sync):
        monkeypatch.setattr(app.config, "DEBUG", False)
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", False)
        built = app.create_app()
        assert isinstance(built, Starlette)
        assert not built.debug

    def test_debug_mode(self, monkeypatch, no_sync, capsys):
        monkeypatch.setattr(app.config, "DEBUG", True)
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", False)
        built = app.create_app()
        assert built.debug
        assert "debug" in capsys.readouterr().out

    def test_syncs_data_by_default(self, monkeypatch, no_sync):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", False)
        app.create_app()
        no_sync.assert_called_once()

    def test_skip_data_sync_skips(self, monkeypatch, no_sync):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", True)
        app.create_app()
        no_sync.assert_not_called()

    def test_missing_data_is_fatal(self, monkeypatch):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", False)
        monkeypatch.setattr(
            app.archive,
            "sync_data",
            MagicMock(side_effect=MissingDataError("no data")),
        )
        with pytest.raises(MissingDataError, match="no data"):
            app.create_app()


class TestRunServer:
    def test_starts_uvicorn_with_config(self, monkeypatch):
        run = MagicMock()
        monkeypatch.setattr(app.uvicorn, "run", run)
        monkeypatch.setattr(app.config, "HOST", "127.0.0.1")
        monkeypatch.setattr(app.config, "PORT", 1234)
        monkeypatch.setattr(app.config, "RELOAD", False)
        monkeypatch.setattr(app.config, "DEBUG", False)
        app.run_server()
        run.assert_called_once()
        assert run.call_args.args == ("holmes.app:create_app",)
        assert run.call_args.kwargs["port"] == 1234
        assert run.call_args.kwargs["factory"] is True
