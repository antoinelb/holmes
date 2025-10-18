import csv

import numpy as np
import pandas as pd
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


def read_projection_info(catchment: str) -> dict[str, list[str]]:
    data = pd.read_pickle(data_dir / f"{catchment}_Projections.pkl")
    return {key: list(val.keys()) for key, val in data.items()}


def read_projection_data(
    catchment: str, climate_model: str, scenario: str, horizon: str
) -> pl.DataFrame:
    if horizon == "REF":
        scenario = "REF"
    else:
        if scenario == "RCP4.5":
            scenario = "R4"
        elif scenario == "RCP8.5":
            scenario = "R4"
        else:
            raise ValueError("`scenario` must be RCP4.5 or RCP8.5.")

    _data = pd.read_pickle(data_dir / f"{catchment}_Projections.pkl")[
        climate_model
    ][horizon]

    keys = sorted(
        [
            (key, int(key.replace(f"{scenario}_memb", "")))
            for key in _data.keys()
            if key.startswith(scenario)
        ],
        key=lambda key: key[1],
    )

    return pl.concat(
        [
            pl.from_pandas(_data["Date"]).rename("date").to_frame(),
            *[
                pl.from_pandas(_data[key]).rename(
                    {
                        "P": f"member_{member}_precipitation",
                        "T": f"member_{member}_temperature",
                    }
                )
                for key, member in keys
            ],
        ],
        how="horizontal",
    )


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
