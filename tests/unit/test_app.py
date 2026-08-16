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


@pytest.fixture
def no_uvicorn(monkeypatch):
    run = MagicMock()
    monkeypatch.setattr(app.uvicorn, "run", run)
    return run


class TestCreateApp:
    def test_builds_starlette_app(self, monkeypatch):
        monkeypatch.setattr(app.config, "DEBUG", False)
        built = app.create_app()
        assert isinstance(built, Starlette)
        assert not built.debug

    def test_debug_mode(self, monkeypatch, capsys):
        monkeypatch.setattr(app.config, "DEBUG", True)
        built = app.create_app()
        assert built.debug
        assert "debug" in capsys.readouterr().out

    # the factory runs inside uvicorn, whose signal handler would swallow a
    # Ctrl-C: syncing there is what made the first-run download unstoppable
    def test_never_syncs_data(self, monkeypatch, no_sync):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", False)
        app.create_app()
        no_sync.assert_not_called()


@pytest.fixture
def no_browser(monkeypatch):
    thread = MagicMock()
    monkeypatch.setattr(app.threading, "Thread", thread)
    return thread


class TestRunServer:
    def test_starts_uvicorn_with_config(
        self, monkeypatch, no_sync, no_uvicorn, no_browser
    ):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", False)
        monkeypatch.setattr(app.config, "HOST", "127.0.0.1")
        monkeypatch.setattr(app.config, "PORT", 1234)
        monkeypatch.setattr(app.config, "RELOAD", False)
        monkeypatch.setattr(app.config, "DEBUG", False)
        app.run_server()
        no_uvicorn.assert_called_once()
        assert no_uvicorn.call_args.args == ("holmes.app:create_app",)
        assert no_uvicorn.call_args.kwargs["port"] == 1234
        assert no_uvicorn.call_args.kwargs["factory"] is True

    def test_syncs_data_before_serving(
        self, monkeypatch, no_sync, no_uvicorn, no_browser
    ):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", False)
        app.run_server()
        no_sync.assert_called_once()

    def test_skip_data_sync_skips(
        self, monkeypatch, no_sync, no_uvicorn, no_browser
    ):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", True)
        app.run_server()
        no_sync.assert_not_called()

    def test_missing_data_is_fatal(self, monkeypatch, no_uvicorn, no_browser):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", False)
        monkeypatch.setattr(
            app.archive,
            "sync_data",
            MagicMock(side_effect=MissingDataError("no data")),
        )
        with pytest.raises(MissingDataError, match="no data"):
            app.run_server()
        no_uvicorn.assert_not_called()

    def test_opens_the_browser_in_production(
        self, monkeypatch, no_sync, no_uvicorn, no_browser
    ):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", True)
        monkeypatch.setattr(app.config, "DEBUG", False)
        monkeypatch.setattr(app.config, "HOST", "127.0.0.1")
        monkeypatch.setattr(app.config, "PORT", 1234)
        app.run_server()
        no_browser.assert_called_once_with(
            target=app._open_browser,
            args=("http://127.0.0.1:1234",),
            daemon=True,
        )
        no_browser.return_value.start.assert_called_once()

    # a browser reopening on every reload is exactly what a dev does not want
    def test_debug_leaves_the_browser_alone(
        self, monkeypatch, no_sync, no_uvicorn, no_browser
    ):
        monkeypatch.setattr(app.config, "SKIP_DATA_SYNC", True)
        monkeypatch.setattr(app.config, "DEBUG", True)
        app.run_server()
        no_browser.assert_not_called()


class TestOpenBrowser:
    def test_opens_the_url(self, monkeypatch):
        monkeypatch.setattr(app, "browser_delay", 0)
        opened = MagicMock()
        monkeypatch.setattr(app.webbrowser, "open", opened)
        app._open_browser("http://127.0.0.1:8000")
        opened.assert_called_once_with("http://127.0.0.1:8000")

    def test_headless_machine_warns_and_serves_on(self, monkeypatch, capsys):
        monkeypatch.setattr(app, "browser_delay", 0)
        monkeypatch.setattr(
            app.webbrowser,
            "open",
            MagicMock(side_effect=RuntimeError("no display")),
        )
        app._open_browser("http://127.0.0.1:8000")
        out = capsys.readouterr().out
        assert "Could not open a browser (no display)" in out
        assert "http://127.0.0.1:8000" in out
