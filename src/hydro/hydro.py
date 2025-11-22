import asyncio
from datetime import datetime, timedelta

import numpy as np
import polars as pl

from src import data
from src.utils.print import format_list

from . import bucket, gr4j, snow
from .utils import hydrological_models


async def precompile() -> None:
    await asyncio.gather(
        gr4j.precompile(), bucket.precompile(), snow.precompile()
    )


def run_model(
    data: pl.DataFrame,
    hydrological_model: str,
    params: dict[str, float | int],
) -> np.ndarray:
    if hydrological_model.lower() == "gr4j":
        return gr4j.run_model(
            data["precipitation"].to_numpy().squeeze(),
            data["evapotranspiration"].to_numpy().squeeze(),
            x1=int(params["x1"]),
            x2=params["x2"],
            x3=int(params["x3"]),
            x4=params["x4"],
        )
    elif hydrological_model.lower() == "bucket":
        return bucket.run_model(
            data["precipitation"].to_numpy().squeeze(),
            data["evapotranspiration"].to_numpy().squeeze(),
            C_soil=params["C_soil"],
            alpha=params["alpha"],
            k_R=params["k_R"],
            delta=params["delta"],
            beta=params["beta"],
            k_T=params["k_T"],
        )
    else:
        raise ValueError(
            "The only available hydrological models are {}.".format(
                format_list(
                    [model.lower() for model in hydrological_models.keys()]
                )
            )
        )


def read_transformed_hydro_data(
    catchment: str,
    start: str,
    end: str,
    snow_model: str,
    *,
    warmup_length: int = 3,
) -> pl.DataFrame:
    warmup_length = 365 * warmup_length

    data_ = data.read_catchment_data(catchment).rename(
        {
            "Date": "date",
            "P": "precipitation",
            "E0": "evapotranspiration",
            "Qo": "flow",
            "T": "temperature",
        },
        strict=False,
    )

    # keep only wanted data plus a warmup period
    data_ = data_.filter(
        pl.col("date").is_between(
            datetime.strptime(start, "%Y-%m-%d")
            - timedelta(days=warmup_length),
            datetime.strptime(end, "%Y-%m-%d"),
        )
    )

    data_ = data_.collect()

    # handle snow
    data_ = data_.with_columns(
        pl.Series(
            "precipitation",
            snow.run_snow_model(data_, snow_model.lower(), catchment),  # type: ignore
        )
    )

    return data_
