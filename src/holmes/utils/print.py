import shutil
from collections.abc import Sized
from typing import Any, Iterable

import click

##########
# public #
##########


def load_print(
    text: str,
    symbol: str = "✱",
    indent: int = 0,
    echo: bool = True,
    end: str = "\r",
) -> None:
    symbol = click.style(f"[{symbol}]", fg="blue")
    if echo:
        print(
            f"\r{' ' * indent}{symbol} {text}".ljust(
                shutil.get_terminal_size().columns
            ),
            end=end,
        )


def done_print(
    text: str,
    symbol: str = "+",
    indent: int = 0,
    echo: bool = True,
) -> None:
    symbol = click.style(f"[{symbol}]", fg="green", bold=True)
    if echo:
        print(
            f"\r{' ' * indent}{symbol} {text}".ljust(
                shutil.get_terminal_size().columns
            )
        )


def load_progress(
    iter_: Iterable[Any],
    text: str,
    indent: int = 0,
    echo: bool = True,
    total: int | None = None,
) -> Iterable[Any]:
    if not echo:
        yield from iter_
        return
    if total is None and isinstance(iter_, Sized):
        total = len(iter_)
    width = len(str(total)) if total is not None else 0
    for i, item in enumerate(iter_, start=1):
        symbol = f"{i:>{width}}/{total}" if total is not None else str(i)
        load_print(text, symbol=symbol, indent=indent)
        yield item
