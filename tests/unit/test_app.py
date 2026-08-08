from unittest.mock import MagicMock

from starlette.applications import Starlette

import holmes.app as app


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
