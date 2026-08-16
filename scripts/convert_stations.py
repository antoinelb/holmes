"""One-shot converter for the MELCC daily station files.

Reads the fixed-width `.txt` files in `data/raw/weather/stations/` and writes
one `{id}_{slug}.csv` per station with columns datetime, lat, lon,
precipitation, tmax, tmin, temperature. Stations missing a parameter entirely
(no temperature or no precipitation gauge) are skipped: the nearest-stations
method needs both.

The produced CSVs are committed: the MELCC `.txt` files they come from have
no public source, so unlike every other input these cannot be refetched, and
`rebuild_completed_stations` needs them on a cold build. They also ship
inside the data release archive built by `holmes package`.

Run as `python scripts/convert_stations.py`.
"""

import sys
from datetime import date
from pathlib import Path

import polars as pl

# station ids are read from the files themselves; names and coordinates come
# from the RSCQ open-data station list and the 1991-2020 climate normals
# (the filenames are mojibake, so they identify nothing)
stations = {
    "7060225": ("pikauba", 47.941860, -71.382225),
    "7061439": ("chicoutimi", 48.307750, -71.211200),
    "7065789": ("saguenay_parc_powell", 48.433895, -71.184586),
    "7066573": ("aux_ecorces", 48.182693, -71.644836),
    "7066611": ("riviere_cyriac", 47.984867, -71.224113),
    "7066820": ("saint_ambroise", 48.586540, -71.353760),
}

stations_dir = Path(__file__).resolve().parents[1] / (
    "data/raw/weather/stations"
)

# MELCC daily fixed-width layout: value is 5 chars, its quality code sits at
# value_start + 6; a blank field means no observation
fields = {"tmax": 21, "tmin": 29, "precipitation": 53}


def run() -> None:
    found: list[str] = []
    for path in sorted(stations_dir.glob("*.txt")):
        id_, data = parse_file(path)
        if id_ not in stations:
            sys.exit(f"Unknown station id {id_} in {path.name}.")
        found.append(id_)
        slug, lat, lon = stations[id_]
        # a station with no record at all for a parameter cannot feed the
        # nearest-stations mean, which needs both
        missing = [
            column
            for column in ("tmax", "tmin", "precipitation")
            if data[column].drop_nulls().is_empty()
        ]
        if missing:
            print(f"Skipping {id_} ({slug}): no {', '.join(missing)} data.")
            continue
        data = data.with_columns(
            pl.lit(lat).alias("lat"),
            pl.lit(lon).alias("lon"),
            ((pl.col("tmax") + pl.col("tmin")) / 2).alias("temperature"),
        ).select(
            "datetime",
            "lat",
            "lon",
            "precipitation",
            "tmax",
            "tmin",
            "temperature",
        )
        check_dates(data, path.name)
        data.write_csv(stations_dir / f"{id_}_{slug}.csv")
        print(f"Wrote {id_}_{slug}.csv ({data.height} days).")

    assert sorted(found) == sorted(stations), (
        f"Expected one file per station; found {sorted(found)}"
    )
    check_known_values()


def parse_file(path: Path) -> tuple[str, pl.DataFrame]:
    rows = []
    for raw in path.read_bytes().splitlines():
        line = raw.decode("latin-1").ljust(60)
        if not line.strip():
            continue
        rows.append(
            {
                "id": line[0:7],
                "datetime": date(
                    int(line[8:12]), int(line[13:15]), int(line[16:18])
                ),
                **{
                    name: parse_value(line[start : start + 5])
                    for name, start in fields.items()
                },
            }
        )
    # explicit schema: some stations open with months of missing values, which
    # would otherwise make inference type the column as null
    data = pl.DataFrame(
        rows,
        schema={
            "id": pl.String,
            "datetime": pl.Date,
            "tmax": pl.Float64,
            "tmin": pl.Float64,
            "precipitation": pl.Float64,
        },
    ).sort("datetime")
    ids = data["id"].unique().to_list()
    assert len(ids) == 1, f"{path.name} mixes station ids {ids}"
    return ids[0], data.drop("id")


def parse_value(field: str) -> float | None:
    field = field.strip()
    return float(field) if field else None


# the files are not dense (Aux Écorces and Rivière-Cyriac drop whole months,
# including the July 1996 flood), so only uniqueness is checked here; the
# loader densifies and backfills from era5
def check_dates(data: pl.DataFrame, name: str) -> None:
    assert data["datetime"].n_unique() == data.height, (
        f"{name}: duplicate dates"
    )


# spot-check one hand-read line per written file
def check_known_values() -> None:
    checks = [
        ("7060225_pikauba.csv", "2009-06-01", 0.0, 16.0, -1.2),
        ("7061439_chicoutimi.csv", "2009-06-12", 0.0, 20.9, 9.6),
        ("7066573_aux_ecorces.csv", "1990-01-01", 5.1, None, None),
        ("7066611_riviere_cyriac.csv", "1990-01-29", 2.6, None, None),
        ("7066820_saint_ambroise.csv", "2010-09-01", 6.4, 33.5, 18.0),
    ]
    for name, day, precipitation, tmax, tmin in checks:
        row = (
            pl.read_csv(stations_dir / name)
            .filter(pl.col("datetime") == day)
            .row(0, named=True)
        )
        expected = {"precipitation": precipitation, "tmax": tmax, "tmin": tmin}
        for column, value in expected.items():
            assert row[column] == value, (
                f"{name} {day} {column}: {row[column]} != {value}"
            )
    print("Spot checks passed.")


if __name__ == "__main__":
    run()
