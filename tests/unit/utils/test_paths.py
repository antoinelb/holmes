import importlib.util
from pathlib import Path

import holmes.utils.paths


class TestPaths:
    def test_paths_resolve_from_module_location(self):
        # a fresh module instance sidesteps the tmp_data_dir patching
        spec = importlib.util.spec_from_file_location(
            "paths_fresh", holmes.utils.paths.__file__
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        root = Path(module.root_dir).resolve()
        assert (root / "pyproject.toml").exists()
        assert (
            Path(module.static_dir).resolve()
            == root / "src" / "holmes" / "static"
        )
        assert Path(module.data_dir).resolve() == root / "data"
        assert Path(module.results_dir).resolve() == root / "data" / "results"
