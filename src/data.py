import csv

import numpy as np
import polars as pl

from src.utils.paths import root_dir

#########
# types #
#########

data_dir = root_dir / "data"

##########
# public #
##########


def get_available_catchments() -> list[tuple[str, bool, tuple[str, str]]]:
    """
    Determines which catchment is available in the data and if snow info is
    available for it.

    Returns
    -------
    list[tuple[str, bool, tuple[str, str]]]
        Each element is a tuple in the format
        (<catchment name>, <snow info is available>, (<period min>, <period max>))
    """
    catchments = [
        file.stem.replace("_Observations", "")
        for file in data_dir.glob("*_Observations.csv")
    ]
    return sorted(
        [
            (
                catchment,
                (data_dir / f"{catchment}_CemaNeigeInfo.csv").exists(),
                _get_available_period(catchment),
            )
            for catchment in catchments
        ],
        key=lambda c: c[0],
    )


def read_catchment_data(catchment: str) -> pl.LazyFrame:
    return pl.scan_csv(
        data_dir / f"{catchment}_Observations.csv"
    ).with_columns(pl.col("Date").str.strptime(pl.Date, "%Y-%m-%d"))


def read_cemaneige_info(catchment: str) -> dict:
    """
    Read CemaNeige configuration parameters for a catchment.

    Parameters
    ----------
    catchment : str
        Catchment name

    Returns
    -------
    dict
        Dictionary with keys: qnbv, altitude_layers, median_altitude, latitude
    """
    path = data_dir / f"{catchment}_CemaNeigeInfo.csv"
    with open(path, "r") as csv_file:
        reader = csv.reader(csv_file)
        info = dict(reader)

    altitude_layers = np.array([float(x) for x in info["AltiBand"].split(";")])

    return {
        "qnbv": float(info["QNBV"]),
        "altitude_layers": altitude_layers,
        "median_altitude": float(info["Z50"]),
        "latitude": float(info["Lat"]),
        "n_altitude_layers": len(altitude_layers),
    }


###########
# private #
###########


def _get_available_period(catchment: str) -> tuple[str, str]:
    """
    Gets the minimum and maximum available dates for the given catchment.

    Parameters
    ----------
    catchment : str
        Catchment name

    Returns
    -------
    str
        Minimum available date
    str
        Maximum available date

    Raises
    ------
    FileNotFoundError
        If the catchment doesn't correspond to an availble data file
    """
    path = data_dir / f"{catchment}_Observations.csv"
    try:
        min_max = (
            pl.scan_csv(path)
            .select(
                pl.col("Date").min().alias("min"),
                pl.col("Date").max().alias("max"),
            )
            .collect()
        )
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"There is no data file '{path}'.") from exc
    return min_max[0, 0], min_max[0, 1]
