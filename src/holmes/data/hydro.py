"""Read-only access to the hydro products.

The server never builds data: every product here is shipped in the data
archive (`holmes.data.archive`) and built by `holmes download`.
"""

import polars as pl

from holmes.data.archive import read_product

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths

#############
# constants #
#############

STATIONS = [
    "061004",
    "061020",
    "061021",
    "061022",
    "061023",
    "061024",
    "061028",
    "061029",
]

##########
# public #
##########


def get_station_data() -> pl.DataFrame:
    return read_product(paths.data_dir / "raw" / "hydro" / "station_data.ipc")


def get_streamflow_data(id: str) -> pl.DataFrame:
    if id not in STATIONS:
        raise ValueError(f"Unknown station {id}.")
    return read_product(
        paths.data_dir / "raw" / "hydro" / "streamflow" / f"{id}.ipc"
    )
