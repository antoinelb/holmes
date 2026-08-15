import asyncio

import typer

from . import app, experiment
from .data import hydro, projection, weather
from .utils.paths import data_dir
from .utils.print import done_print

############
# external #
############


def run_cli() -> None:
    cli = _init_cli()
    cli()


############
# internal #
############


def _init_cli() -> typer.Typer:
    cli = typer.Typer(
        context_settings={"help_option_names": ["-h", "--help"]},
        pretty_exceptions_enable=False,
        pretty_exceptions_show_locals=False,
        invoke_without_command=True,
    )
    cli.callback()(_default)
    cli.command("run")(_run)
    cli.command("r", hidden=True)(_run)
    cli.command("download")(_download)
    cli.command("d", hidden=True)(_download)
    cli.command("experiment")(_run_experiments)
    cli.command("e", hidden=True)(_run_experiments)
    return cli


def _default(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _run()


def _run() -> None:
    """
    (r) Runs the dashboard.
    """
    app.run_server()


def _download(
    force: bool = typer.Option(
        False, "--force", "-f", help="Rebuild files that are already here."
    ),
) -> None:
    """
    (d) Rebuilds the datasets served from the repo from their true source.

    This is the maintainer path: it downloads the ERA5 cells from Copernicus
    and writes the era5.ipc that the repo serves, plus the per-station
    stations_backfill.ipc sampled from the ministry grids and ERA5 cells, so
    it needs CDS credentials on a cold cell cache. Running the app never
    needs it — missing published files are fetched from the repo on first
    use. It also prefetches the projection products (ClimEx and
    ESPO-G6-R2) for every station: those are not published (PAVICS needs
    no credentials), but a cold build takes several minutes, so it is
    done deliberately here rather than lazily on first use.
    """
    stations = asyncio.run(hydro.get_station_data())

    era5_path = data_dir / "raw" / "weather" / "era5.ipc"
    if era5_path.exists() and not force:
        done_print(
            f"Already have {era5_path.name}; pass --force to rebuild it."
        )
    else:
        weather.read_weather_data(stations, method="era5", rebuild=True)

    backfill_path = data_dir / "raw" / weather.stations_backfill_file
    if backfill_path.exists() and not force:
        done_print(
            f"Already have {backfill_path.name}; pass --force to rebuild it."
        )
    else:
        weather.rebuild_stations_backfill()

    if projection.has_projection_data(stations) and not force:
        done_print(
            "Already have the projection products; pass --force to rebuild "
            "them."
        )
    else:
        asyncio.run(projection.read_projection_data(stations, rebuild=force))


def _run_experiments() -> None:
    """
    (e) Runs the experiments.
    """
    asyncio.run(experiment.run_experiment())
