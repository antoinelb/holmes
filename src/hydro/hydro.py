import polars as pl

from src.utils.print import format_list

from . import gr4j, snow
from .utils import hydrological_models


async def precompile() -> None:
    await gr4j.precompile()
    await snow.precompile()


def run_model(
    data: pl.DataFrame,
    hydrological_model: str,
    params: dict[str, float | int],
) -> pl.DataFrame:
    if hydrological_model.lower() == "gr4j":
        simulation = gr4j.run_model(
            data["precipitation"].to_numpy().squeeze(),
            data["evapotranspiration"].to_numpy().squeeze(),
            x1=int(params["x1"]),
            x2=params["x2"],
            x3=int(params["x3"]),
            x4=params["x4"],
        )
    else:
        raise ValueError(
            "The only available hydrological models are {}.".format(
                format_list(
                    [model.lower() for model in hydrological_models.keys()]
                )
            )
        )
    return data.with_columns(pl.Series("simulation", simulation))
