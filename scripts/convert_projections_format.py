from pathlib import Path

import pandas as pd
import polars as pl

from holmes.utils import paths


def main() -> None:
    for path in paths.data_dir.glob("*_Projections.pkl"):
        convert_projection_format(path)


def convert_projection_format(path: Path) -> None:
    data = pd.read_pickle(path)
    dataframes: list[pl.DataFrame] = []
    for model, model_values in data.items():
        for horizon, horizon_values in model_values.items():
            dates = (
                pl.from_pandas(horizon_values["Date"])
                .rename("date")
                .dt.date()
                .to_frame()
            )
            dataframes.append(
                pl.concat(
                    [
                        pl.concat(
                            [
                                dates,
                                pl.from_pandas(values)
                                .rename(
                                    {
                                        "P": "precipitation",
                                        "T": "temperature",
                                    }
                                )
                                .with_columns(
                                    pl.lit(
                                        f"{int(key.split('_')[1].replace('memb', '')):02d}"
                                    ).alias("member"),
                                    pl.lit(
                                        "REF"
                                        if horizon == "REF"
                                        else "RCP"
                                        + key.split("_")[0][1]
                                        + ".5"
                                    ).alias("scenario"),
                                    pl.lit(model).alias("model"),
                                    pl.lit(horizon).alias("horizon"),
                                ),
                            ],
                            how="horizontal",
                        )
                        for key, values in horizon_values.items()
                        if key != "Date"
                    ]
                )
            )
    _data = pl.concat(dataframes)
    _data.write_csv(path.parent / (path.stem + ".csv"))


if __name__ == "__main__":
    main()
