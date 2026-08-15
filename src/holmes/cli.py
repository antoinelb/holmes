import asyncio
import importlib
from pathlib import Path
from types import ModuleType

import typer

from . import app, experiment
from .utils.print import fail_print

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
    cli.command("package")(_package)
    cli.command("p", hidden=True)(_package)
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
    (d) Builds every data product incrementally from its true source.

    This is the maintainer path: running the app never needs it — the
    server refreshes its local products from the published archive at
    startup. Building needs the `download` extra and, on a cold ERA5
    cell cache, CDS credentials.
    """
    download = _import_download_module("holmes.download")
    download.run_download(force=force)


def _package(
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Path of the archive to write."
    ),
) -> None:
    """
    (p) Zips every built product into the dated release archive.
    """
    package = _import_download_module("holmes.download.package")
    package.build_archive(output)


def _run_experiments() -> None:
    """
    (e) Runs the experiments.
    """
    asyncio.run(experiment.run_experiment())


def _import_download_module(name: str) -> ModuleType:
    # lazy so the CLI never pays for the heavy build stack (xarray, cdsapi,
    # ...) unless a build command actually runs
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        fail_print(
            f"Could not import {name} ({exc}); building data products "
            "needs the download extra: pip install 'holmes-hydro[download]'."
        )
        raise typer.Exit(1) from exc
