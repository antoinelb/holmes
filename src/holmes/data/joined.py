"""Read-only access to the joined station + streamflow + weather products.

The server never builds data: every product here is shipped in the data
archive (`holmes.data.archive`) and built by `holmes download`
(`holmes.download.joined`).
"""

import polars as pl

from holmes.data.archive import read_product
from holmes.data.weather import WeatherMethod, validate_n_stations

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths

##########
# public #
##########


def read_joined_data(
    *, method: WeatherMethod, n_stations: int = 3
) -> pl.DataFrame:
    validate_n_stations(n_stations)
    # only the nearest-stations product depends on the station count, so
    # only its product name carries it
    suffix = f"_{n_stations}" if method == "nearest_stations" else ""
    return read_product(paths.data_dir / "raw" / f"data_{method}{suffix}.ipc")
