from pathlib import Path

root_dir = Path(__file__).parent / ".." / ".." / ".."
# package-relative so it also resolves in installed (non src-layout) wheels
static_dir = Path(__file__).parent / ".." / "static"
data_dir = root_dir / "data"
results_dir = root_dir / "data" / "results"
