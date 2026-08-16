from datetime import date
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


def fetched_today(path: Path) -> bool:
    """True when `path` exists and was last written today, local time.

    The sources that are refetched every run only grow as days accrue, so
    a second run on the same day would download identical bytes. mtime is
    trusted: every writer here stages a `.part` and renames it, which
    carries the staged file's own mtime.
    """
    return (
        path.exists()
        and date.fromtimestamp(path.stat().st_mtime) == date.today()
    )
