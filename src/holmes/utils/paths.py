from pathlib import Path

import platformdirs

from holmes import config

root_dir = Path(__file__).parent / ".." / ".." / ".."
# package-relative so it also resolves in installed (non src-layout) wheels
static_dir = Path(__file__).parent / ".." / "static"
# data lives outside the package so installed copies never write into
# site-packages; a repo checkout opts back in with HOLMES_DATA_DIR=data
data_dir = (
    Path(config.DATA_DIR).expanduser().resolve()
    if config.DATA_DIR
    else Path(platformdirs.user_data_dir("holmes"))
)
results_dir = data_dir / "results"
