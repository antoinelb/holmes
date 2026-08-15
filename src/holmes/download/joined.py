"""Joined station + streamflow + weather products for the server.

One pre-joined frame per weather method (era5, ministry_grid and the
five nearest-station slider positions); the server's calibration path
(`holmes.data.joined.read_joined_data`) reads these frames without ever
joining anything itself.
"""

from pathlib import Path

import polars as pl

from holmes.data.archive import MissingDataError
from holmes.download.weather import max_n_stations, min_n_stations

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths
from holmes.utils.print import progress_task

##########
# public #
##########


def build_joined_data(stations: pl.DataFrame) -> None:
    """Join streamflow and weather onto every station, per weather method.

    Always rebuilds every product: the joins are cheap and local, and
    the inputs may have just been refreshed. Inputs are read from disk
    directly — the orchestrator's earlier steps guarantee them — and a
    missing one raises rather than producing a partial product.
    """
    if "id" not in stations.columns or stations.height == 0:
        raise ValueError("No stations to build joined data for.")

    names = [
        "era5",
        "ministry_grid",
        *(
            f"nearest_stations_{n}"
            for n in range(min_n_stations, max_n_stations + 1)
        ),
    ]
    streamflow = _read_streamflow(stations)
    with progress_task(
        "Building the joined products...",
        f"Built {len(names)} joined products.",
        total=len(names),
    ) as current:
        for name in names:
            weather = _read_product(
                paths.data_dir / "raw" / "weather" / f"{name}.ipc"
            )
            _write_ipc(
                paths.data_dir / "raw" / f"data_{name}.ipc",
                _join(stations, weather, streamflow),
            )
            current.increment()


###########
# private #
###########


def _join(
    stations: pl.DataFrame,
    weather: pl.DataFrame,
    streamflow: pl.DataFrame,
) -> pl.DataFrame:
    """The join every downstream consumer reads prebuilt."""
    return (
        stations.select("id", "name", "lat", "lon", "area", "elevation_layers")
        # weather-left so days outside the observed record are kept
        # (streamflow null there), letting simulation reconstruct
        # unobserved periods; weather availability is the real limit
        .join(
            weather.with_columns(pl.col("datetime").dt.date()).join(
                streamflow, on=["id", "datetime"], how="left"
            ),
            on="id",
        )
        .fill_nan(None)
    )


def _read_streamflow(stations: pl.DataFrame) -> pl.DataFrame:
    return pl.concat(
        [
            _read_product(
                paths.data_dir / "raw" / "hydro" / "streamflow" / f"{id}.ipc"
            )
            for id in stations["id"]
        ]
    )


def _read_product(path: Path) -> pl.DataFrame:
    if not path.exists():
        raise MissingDataError(
            f"Missing {path}; the orchestrator steps before the join must "
            "have built it."
        )
    return pl.read_ipc(path, memory_map=False)


def _write_ipc(path: Path, data: pl.DataFrame) -> None:
    """Stage then atomically replace, so a crash never leaves a torn file."""
    path.parent.mkdir(exist_ok=True, parents=True)
    staged = path.with_suffix(".part")
    data.write_ipc(staged, compression="zstd")
    staged.replace(path)
