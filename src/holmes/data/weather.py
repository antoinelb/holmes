"""Read-only access to the weather products.

The server never builds data: every product here is shipped in the data
archive (`holmes.data.archive`) and built by `holmes download`.
"""

from typing import Literal

import polars as pl

from holmes.data.archive import read_product

# paths is imported as a module (not `from ... import data_dir`) so tests
# patching `holmes.utils.paths.data_dir` reach this module too
from holmes.utils import paths

#########
# types #
#########

WeatherMethod = Literal["nearest_stations", "era5", "ministry_grid"]

#############
# constants #
#############

# The MELCC daily station files behind nearest_stations were hand-delivered
# for the TP and have no public source; ids, names and coordinates come from
# the RSCQ open-data station list and the 1991-2020 climate normals.
stations_files = {
    "7060225": ("weather/stations/7060225_pikauba.csv", "Pikauba"),
    "7061439": ("weather/stations/7061439_chicoutimi.csv", "Chicoutimi"),
    "7066573": ("weather/stations/7066573_aux_ecorces.csv", "Aux Écorces"),
    "7066611": (
        "weather/stations/7066611_riviere_cyriac.csv",
        "Rivière-Cyriac",
    ),
    "7066820": (
        "weather/stations/7066820_saint_ambroise.csv",
        "Saint-Ambroise",
    ),
}

# the per-station reference series completing the observed records: the
# ministry-grid cell over each station where the grids have the day, the
# station's era5 cell otherwise
stations_backfill_file = "weather/stations_backfill.ipc"

# nearest-station picks are bounded by the UI slider
min_n_stations = 1
max_n_stations = 5

##########
# public #
##########


def read_weather_data(
    *, method: WeatherMethod, n_stations: int = 3
) -> pl.DataFrame:
    validate_n_stations(n_stations)
    # the station count changes the nearest-stations product, so it is part
    # of its product name; the grid methods ignore it
    name = (
        f"nearest_stations_{n_stations}"
        if method == "nearest_stations"
        else method
    )
    return read_product(paths.data_dir / "raw" / "weather" / f"{name}.ipc")


def read_weather_grid(*, method: WeatherMethod) -> pl.DataFrame:
    """Cells or stations feeding each watershed mean, for the map.

    nearest_stations always ships the full station pool, whatever the
    slider says, so its grid product carries no station count.
    """
    return read_product(
        paths.data_dir / "raw" / "weather" / f"grid_{method}.ipc"
    )


def validate_n_stations(n_stations: int) -> None:
    # public because `holmes.data.joined` guards its product name with the
    # same bounds
    if not min_n_stations <= n_stations <= max_n_stations:
        raise ValueError(
            f"n_stations must be between {min_n_stations} and "
            f"{max_n_stations}, got {n_stations}."
        )
