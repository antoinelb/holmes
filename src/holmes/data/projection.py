"""Read-only access to the projection products.

The server never builds data: every product here is shipped in the data
archive (`holmes.data.archive`) and built by `holmes download`.
"""

from pathlib import Path

import polars as pl

from holmes.data.archive import read_product

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths

#############
# constants #
#############

# both ensembles are clipped to the same window, so every scenario/member
# series starts on this year; the projection bench derives its warmup
# horizon from it
projection_start_year = 2020

##########
# public #
##########


def has_projection_data(stations: pl.DataFrame) -> bool:
    """Whether every given station has its local product."""
    return all(_product_path(id_).exists() for id_ in stations["id"])


def read_projection_data(stations: pl.DataFrame) -> pl.DataFrame:
    """Daily projected forcing averaged over each station's watershed.

    `stations` is the station frame filtered to the wanted ids. Returns one
    row per station, ensemble, scenario, member and day, with precipitation
    in mm/day and temperature in deg C on a noleap calendar (no Feb 29
    rows — fine downstream, the models only use the day of year).
    """
    if stations.height == 0:
        raise ValueError("No stations to read projection data for.")
    return pl.concat(
        [read_product(_product_path(id_)) for id_ in stations["id"]]
    ).sort("id", "ensemble", "scenario", "member", "datetime")


###########
# private #
###########


def _product_path(id_: str) -> Path:
    return paths.data_dir / "raw" / "projection" / f"{id_}.ipc"
