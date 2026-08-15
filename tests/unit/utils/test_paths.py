import importlib.util
from pathlib import Path
from types import ModuleType

import platformdirs

import holmes.config
import holmes.utils.paths


class TestPaths:
    def test_paths_resolve_from_module_location(self):
        module = _load_fresh_paths()

        root = Path(module.root_dir).resolve()
        assert (root / "pyproject.toml").exists()
        assert (
            Path(module.static_dir).resolve()
            == root / "src" / "holmes" / "static"
        )

    def test_data_dir_from_env_var(self, monkeypatch):
        # "~" proves the value is user-expanded, not taken literally
        monkeypatch.setattr(holmes.config, "DATA_DIR", "~/holmes-data")
        module = _load_fresh_paths()

        expected = Path("~/holmes-data").expanduser().resolve()
        assert module.data_dir == expected
        assert module.results_dir == expected / "results"

    def test_data_dir_defaults_to_user_data_dir(self, monkeypatch):
        monkeypatch.setattr(holmes.config, "DATA_DIR", "")
        module = _load_fresh_paths()

        expected = Path(platformdirs.user_data_dir("holmes"))
        assert module.data_dir == expected
        assert module.results_dir == expected / "results"


def _load_fresh_paths() -> ModuleType:
    # a fresh module instance re-runs the import-time resolution against the
    # (possibly monkeypatched) shared holmes.config, and sidesteps the
    # tmp_data_dir patching of the real module
    spec = importlib.util.spec_from_file_location(
        "paths_fresh", holmes.utils.paths.__file__
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
