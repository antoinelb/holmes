"""Server-side sync of the published data archive.

The server never builds data: a daily GitHub Actions cron publishes one
dated zip of everything (`data-YYYY-MM-DD.zip`) on the repo's rolling
`data` release, and `sync_data` (called once at startup) downloads and
extracts it when a newer one exists.
"""

import os
import re
import shutil
import zipfile
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import httpx
import polars as pl

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths
from holmes.utils.print import Task, progress_task, task, warn_print

#############
# constants #
#############

release_api_url = (
    "https://api.github.com/repos/antoinelb/holmes/releases/tags/data"
)

asset_pattern = re.compile(r"^data-(\d{4}-\d{2}-\d{2})\.zip$")

# records the date of the archive currently extracted, at
# `data_dir / marker_name`
marker_name = "archive_date.txt"

# a file every real archive contains; its absence means an extraction is
# truncated or not a holmes data archive at all
sentinel = Path("raw/hydro/station_data.ipc")

# the download counter is reported in whole megabytes, decimal ones so it
# matches the archive size the release page advertises
mb = 1_000_000

missing_data_help = (
    "The server never builds data: run `holmes download` (maintainers, "
    "needs credentials) or restart with network access so the startup "
    "sync can fetch the archive from the `data` release."
)

##########
# public #
##########


class MissingDataError(RuntimeError):
    """Raised when a data product is absent locally and cannot be
    obtained."""


def sync_data() -> None:
    """Download and extract the latest data archive if newer than local.

    Called once at server startup. A failed sync never corrupts existing
    data: every download and extraction happens in a staging directory
    under `data_dir` and files are swapped in with atomic renames.
    """
    local = local_archive_date()

    try:
        remote_date, url = _find_latest_asset()
    except Exception as exc:
        _handle_sync_failure(f"check the data release ({exc})")
        return

    if local is not None and local >= remote_date:
        return

    staging = paths.data_dir / "tmp"
    try:
        with task(
            _sync_message(local),
            f"Downloaded data archive ({remote_date.isoformat()}).",
        ):
            archive = _download_archive(url, remote_date, staging)
            extract_dir = _extract_archive(archive, staging)
    except Exception as exc:
        # staging holds only this failed attempt; dropping it keeps a
        # persistent failure from stranding a partial archive on disk
        shutil.rmtree(staging, ignore_errors=True)
        _handle_sync_failure(f"download the data archive ({exc})")
        return
    except BaseException:
        # a Ctrl-C mid-download would otherwise strand hundreds of
        # megabytes of partial archive on disk
        shutil.rmtree(staging, ignore_errors=True)
        raise

    _install_extracted(extract_dir)
    _write_marker(remote_date)
    shutil.rmtree(staging)


def read_product(path: Path) -> pl.DataFrame:
    """Read one data product, raising `MissingDataError` if absent."""
    if path.exists():
        # the archives hold compressed IPC files; mapping is unavailable on
        # them and polars warns loudly about it
        return pl.read_ipc(path, memory_map=False)
    raise MissingDataError(f"Missing data product {path}. {missing_data_help}")


def local_archive_date() -> date | None:
    """Parse the archive marker, returning None if absent or garbled."""
    marker = paths.data_dir / marker_name
    try:
        return date.fromisoformat(marker.read_text().strip())
    except (OSError, ValueError):
        return None


###########
# private #
###########


def _find_latest_asset() -> tuple[date, str]:
    """Return the date and download url of the newest dated archive."""
    response = httpx.get(
        release_api_url,
        timeout=30,
        follow_redirects=True,
        headers={"Accept": "application/vnd.github+json"},
    )
    response.raise_for_status()

    assets: dict[date, str] = {}
    for asset in response.json().get("assets", []):
        match = asset_pattern.match(asset.get("name", ""))
        if match is not None:
            assets[date.fromisoformat(match.group(1))] = asset[
                "browser_download_url"
            ]
    if not assets:
        raise ValueError("no data-YYYY-MM-DD.zip asset on the data release")

    latest = max(assets)
    return latest, assets[latest]


def _handle_sync_failure(action: str) -> None:
    """Warn if existing local data keeps the server usable, raise
    otherwise."""
    if (paths.data_dir / sentinel).exists():
        warn_print(f"Could not {action}; using existing local data.")
        return
    raise MissingDataError(
        f"No local data found and could not {action}. {missing_data_help}"
    )


def _sync_message(local: date | None) -> str:
    """Say what the wait is for, and that a first run only waits once.

    A garbled marker also reads as no local date, so the promise of a
    one-time wait is made on the data itself being absent.
    """
    if local is None and not (paths.data_dir / sentinel).exists():
        return (
            "Downloading the data (first run only, a few minutes); the "
            "app starts as soon as it is done"
        )
    return "Updating the data to the latest archive"


def _download_archive(url: str, remote_date: date, staging: Path) -> Path:
    """Stream the archive to staging, only renaming a complete download."""
    staging.mkdir(parents=True, exist_ok=True)
    archive = staging / f"data-{remote_date.isoformat()}.zip"
    staged = staging / f"{archive.name}.part"

    # the archive is hundreds of MB, so it is streamed to disk rather than
    # buffered in memory
    with httpx.stream(
        "GET", url, timeout=300, follow_redirects=True
    ) as response:
        response.raise_for_status()
        total = _declared_megabytes(response.headers)
        with _download_task(total) as progress:
            written = 0
            reported = 0
            with staged.open("wb") as file:
                for chunk in response.iter_bytes():
                    file.write(chunk)
                    written += len(chunk)
                    # one tick per whole megabyte, clamped so a server
                    # undercounting content-length cannot overrun the total
                    while reported < min(written // mb, total):
                        reported += 1
                        progress.increment()

    staged.replace(archive)
    return archive


def _declared_megabytes(headers: Mapping[str, str]) -> int:
    """Size the counter, returning 0 for an absent or unparsable header.

    The counter is display only: a server sending a junk content-length
    must cost the progress bar, never the download.
    """
    try:
        return int(headers.get("content-length", 0)) // mb
    except (TypeError, ValueError):
        return 0


def _download_task(total: int) -> Task:
    """Count megabytes when the server declares a size, else just wait."""
    done = "Downloaded the archive."
    if total > 0:
        return progress_task("MB downloaded", done, total)
    return task("Downloading the archive", done)


def _extract_archive(archive: Path, staging: Path) -> Path:
    """Extract the archive under staging, validating members and content."""
    extract_dir = staging / "extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)

    root = extract_dir.resolve()
    with (
        task("Extracting the archive", "Extracted the archive."),
        zipfile.ZipFile(archive) as file,
    ):
        for member in file.namelist():
            # zip-slip guard: a member must never escape the extract dir
            if not (extract_dir / member).resolve().is_relative_to(root):
                raise ValueError(f"unsafe member path {member} in archive")
            file.extract(member, extract_dir)

        # a truncated or wrong zip would otherwise replace real data
        if not (extract_dir / sentinel).exists():
            raise ValueError(
                f"archive is missing {sentinel}; it is truncated or not a "
                "data archive"
            )
    return extract_dir


def _install_extracted(extract_dir: Path) -> None:
    """Move every extracted file into place with atomic renames.

    Staging lives under `data_dir`, so source and destination share a
    filesystem and concurrent readers always see a valid file.
    """
    for src in sorted(extract_dir.rglob("*")):
        if not src.is_file():
            continue
        dest = paths.data_dir / src.relative_to(extract_dir)
        dest.parent.mkdir(parents=True, exist_ok=True)
        os.replace(src, dest)


def _write_marker(remote_date: date) -> None:
    marker = paths.data_dir / marker_name
    staged = marker.parent / f"{marker.name}.part"
    staged.write_text(remote_date.isoformat() + "\n")
    staged.replace(marker)
