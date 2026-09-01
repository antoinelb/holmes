"""Packaging of the built products into the dated data archive.

A daily cron zips every product `archive_manifest` lists into
`data-YYYY-MM-DD.zip` on the repo's rolling `data` release; the server's
startup sync (`holmes.data.archive`) downloads and extracts it.
"""

import zipfile
from datetime import date
from pathlib import Path

from holmes.data.archive import MissingDataError
from holmes.data.hydro import STATIONS
from holmes.data.weather import stations_backfill_file, stations_files
from holmes.download.tiles import tile_paths
from holmes.download.weather import max_n_stations, min_n_stations

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths
from holmes.utils.print import done_print, progress_task

##########
# public #
##########


def archive_manifest() -> list[Path]:
    """Every product an archive must contain, relative to `data_dir`.

    Derived from the same constants the builders use, so adding a
    station or a MELCC csv extends the manifest without a second edit
    here.
    """
    raw = Path("raw")
    weather = raw / "weather"
    n_range = range(min_n_stations, max_n_stations + 1)
    return [
        raw / "hydro" / "station_data.ipc",
        *(raw / "hydro" / "streamflow" / f"{id}.ipc" for id in STATIONS),
        weather / "era5.ipc",
        weather / "ministry_grid.ipc",
        *(weather / f"nearest_stations_{n}.ipc" for n in n_range),
        weather / "grid_era5.ipc",
        weather / "grid_ministry_grid.ipc",
        weather / "grid_nearest_stations.ipc",
        raw / stations_backfill_file,
        *(raw / name for name, _ in stations_files.values()),
        *(
            weather / "stations_completed" / f"{climate_id}.ipc"
            for climate_id in stations_files
        ),
        *(raw / "projection" / f"{id}.ipc" for id in STATIONS),
        raw / "data_era5.ipc",
        raw / "data_ministry_grid.ipc",
        *(raw / f"data_nearest_stations_{n}.ipc" for n in n_range),
        *tile_paths(),
    ]


def build_archive(output: Path | None = None) -> Path:
    """Zip every manifest product into the dated release archive.

    The full manifest is verified first, raising with every absentee at
    once, so a broken build reports everything wrong in one run rather
    than one file per day.
    """
    if output is None:
        output = Path.cwd() / f"data-{date.today():%Y-%m-%d}.zip"

    manifest = archive_manifest()
    missing = [
        entry for entry in manifest if not (paths.data_dir / entry).exists()
    ]
    if missing:
        raise MissingDataError(
            f"Cannot build the archive; {len(missing)} products are "
            "missing: " + ", ".join(str(entry) for entry in missing) + "."
        )

    staged = output.with_suffix(".part")
    with progress_task(
        "Packaging the data archive...",
        f"Packaged {len(manifest)} products.",
        total=len(manifest),
    ) as current:
        # streamed file by file: the archive is hundreds of MB, so the
        # products are never buffered in memory
        with zipfile.ZipFile(staged, "w", zipfile.ZIP_DEFLATED) as archive:
            for entry in manifest:
                archive.write(paths.data_dir / entry, entry.as_posix())
                current.increment()
    staged.replace(output)
    done_print(f"Built {output.name}.")
    return output
