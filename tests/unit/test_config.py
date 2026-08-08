import importlib

import holmes.config


class TestConfig:
    def test_defaults_without_env_file(self, tmp_path, monkeypatch):
        # config reads .env relative to cwd at import time, so reload from an
        # empty directory to see the defaults
        monkeypatch.chdir(tmp_path)
        try:
            module = importlib.reload(holmes.config)
            assert module.DEBUG is False
            assert module.RELOAD is False
            assert module.PORT == 8000
            assert module.HOST == "127.0.0.1"
        finally:
            monkeypatch.undo()
            importlib.reload(holmes.config)

    def test_environment_overrides(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("RELOAD", "true")
        monkeypatch.setenv("PORT", "1234")
        monkeypatch.setenv("HOST", "0.0.0.0")
        try:
            module = importlib.reload(holmes.config)
            assert module.DEBUG is True
            assert module.RELOAD is True
            assert module.PORT == 1234
            assert module.HOST == "0.0.0.0"
        finally:
            monkeypatch.undo()
            importlib.reload(holmes.config)
