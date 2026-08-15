import re
import shutil
import sys
import threading
import time
from collections.abc import Iterable, Sized
from dataclasses import dataclass, field
from types import TracebackType
from typing import Any, Literal, assert_never

#############
# constants #
#############

blue = "\x1b[34m"
bold_green = "\x1b[1;32m"
bold_yellow = "\x1b[1;33m"
bold_red = "\x1b[1;31m"
normal = "\x1b[0m"
erase_line = "\r\x1b[2K"

_colour = re.compile(r"\x1b\[[0-9;]*m")

#########
# types #
#########

# "tty": cursor escapes work; "notebook": the frontend rewrites a line
# on \r but ignores cursor escapes; "plain": append-only (logs, files)
_Mode = Literal["tty", "notebook", "plain"]


def _detect_mode() -> _Mode:
    if sys.stdout.isatty():
        return "tty"
    # ipykernel's OutStream is not a tty, yet the notebook frontend
    # still honours a bare \r — that is how tqdm redraws in a cell
    if type(sys.stdout).__module__.startswith("ipykernel"):
        return "notebook"
    return "plain"


@dataclass
class _Pending:
    id: int
    msg: str
    indent: int


@dataclass
class _Progress:
    id: int
    msg: str
    done: int
    total: int
    indent: int


# All mutable display state, behind one lock (_lock): the bottom line of
# the screen is a pure function of this state (_render_bottom_line) and
# is redrawn after every mutation, so screen == render(state) whenever
# the lock is released.
# Blocks (task, progress_task, closing) belong to the orchestrating
# thread; worker threads may only increment.
@dataclass
class _PrintState:
    indent: int = 0
    pending: _Pending | None = None
    progress: _Progress | None = None
    next_id: int = 0
    # sampled once at first state creation: output redirected mid-run
    # keeps the original mode
    mode: _Mode = field(default_factory=_detect_mode)
    # notebook only: visible width of the line \r will overwrite
    last_width: int = 0


class Task:
    def __init__(self, id: int, msg: str, done_msg: str) -> None:
        self.id = id
        self.msg = msg
        self.done_msg = done_msg
        self.started = time.monotonic()

    def __enter__(self) -> "Task":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self._close("+", bold_green, success=True)
        else:
            self._close("x", bold_red, success=False)

    def done_with(self, done_msg: str) -> None:
        # for a closing message the task could not know when it opened —
        # a tally of the work it just did
        self.done_msg = done_msg

    def increment(self) -> None:
        with _lock:
            progress = _state.progress
            if progress is not None and progress.id == self.id:
                progress.done += 1
            _write(_state, None)

    def _close(self, symbol: str, colour: str, *, success: bool) -> None:
        with _lock:
            state = _state
            state.indent = max(state.indent - 1, 0)
            msg = self.done_msg if success else self.msg
            elapsed = f"[{time.monotonic() - self.started:.1f}s]"
            painted = _paint_symbol(symbol, colour)

            if state.progress is not None and state.progress.id == self.id:
                state.progress = None

            if state.pending is not None and state.pending.id == self.id:
                state.pending = None
            line = _format_line(state.indent, msg, painted)

            _write(
                state,
                _format_close_line(state.mode == "tty", line, elapsed),
            )


_lock = threading.Lock()
_state = _PrintState()

##########
# public #
##########


def task(msg: str, done_msg: str) -> Task:
    with _lock:
        state = _state
        _materialize_pending(state)
        task_id = state.next_id
        state.next_id += 1
        state.pending = _Pending(id=task_id, msg=msg, indent=state.indent)
        state.indent += 1
        _write(state, None)
    return Task(task_id, msg, done_msg)


def progress_task(msg: str, done_msg: str, total: int) -> Task:
    with _lock:
        state = _state
        _materialize_pending(state)

        # one counted task at a time; nested counters would need a
        # progress stack (list, render the last, increment by id)
        collision = state.progress is not None
        if collision:
            _write(
                state,
                _format_line(
                    state.indent,
                    "A progress task already exists.",
                    _paint_symbol("!", bold_yellow),
                ),
            )

        task_id = state.next_id
        state.next_id += 1
        state.pending = _Pending(id=task_id, msg=msg, indent=state.indent)

        if not collision:
            state.progress = _Progress(
                id=task_id,
                msg=msg,
                done=0,
                total=total,
                indent=state.indent + 1,
            )

        state.indent += 1
        _write(state, None)
    return Task(task_id, msg, done_msg)


def done_print(
    msg: str,
    symbol: str = "+",
    indent: int = 0,
    echo: bool = True,
) -> None:
    # symbol/indent/echo are compatibility shims for the legacy API;
    # deleted with the data-layer split
    if echo:
        _print_permanent(msg, symbol, bold_green, legacy_indent=indent)


def warn_print(msg: str) -> None:
    _print_permanent(msg, "!", bold_yellow)


def fail_print(msg: str) -> None:
    _print_permanent(msg, "x", bold_red)


# compatibility shims for the legacy API; deleted with the data-layer split


def load_print(
    text: str,
    symbol: str = "✱",
    indent: int = 0,
    echo: bool = True,
    end: str = "\r",
) -> None:
    if echo:
        print(
            f"\r{' ' * indent}{_paint_symbol(symbol, blue)} {text}".ljust(
                shutil.get_terminal_size().columns
            ),
            end=end,
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


###########
# private #
###########


def _print_permanent(
    msg: str, symbol: str, colour: str, legacy_indent: int = 0
) -> None:
    with _lock:
        _materialize_pending(_state)
        _write(
            _state,
            " " * legacy_indent
            + _format_line(_state.indent, msg, _paint_symbol(symbol, colour)),
        )


def _materialize_pending(state: _PrintState) -> None:
    pending = state.pending
    if pending is not None:
        state.pending = None
        _write(
            state,
            _format_line(
                pending.indent, pending.msg, _paint_symbol("→", blue)
            ),
        )


# exactly one transient line, always the bottom one; rewriting anything
# above it (e.g. one live line per worker, or turning a materialized [→]
# back into [+]) would need pacman-style relative cursor tracking
def _render_bottom_line(state: _PrintState) -> str | None:
    pending = state.pending
    progress = state.progress
    if (
        pending is not None
        and progress is not None
        and pending.id == progress.id
    ):
        return _format_line(
            pending.indent,
            pending.msg,
            _paint_symbol(
                _format_progress_symbol(progress.done, progress.total),
                blue,
            ),
        )
    if pending is not None:
        return _format_line(
            pending.indent, pending.msg, _paint_symbol("∗", blue)
        )
    if progress is not None:
        return _format_line(
            progress.indent,
            progress.msg,
            _paint_symbol(
                _format_progress_symbol(progress.done, progress.total),
                blue,
            ),
        )
    return None


def _write(state: _PrintState, permanent: str | None) -> None:
    # display is non-critical: a broken pipe must never kill the run
    try:
        sys.stdout.write(_render_output(state, permanent))
        sys.stdout.flush()
    except OSError:
        pass


def _render_output(state: _PrintState, permanent: str | None) -> str:
    output = ""
    match state.mode:
        case "tty":
            output += erase_line
        case "notebook":
            output += "\r"
        case "plain":
            pass
        case _:  # pragma: no cover
            assert_never(state.mode)

    if permanent is not None:
        output += _erase_tail(state, permanent) + "\n"
        # the newline ends the rewritable line: nothing left to cover
        state.last_width = 0
    if state.mode != "plain":
        output += _erase_tail(state, _render_bottom_line(state) or "")
    return output


# the notebook frontend has no erase-line: after a \r it keeps whatever
# the new text does not cover, so pad the shorter line with blanks
def _erase_tail(state: _PrintState, line: str) -> str:
    if state.mode != "notebook":
        return line
    width = len(_colour.sub("", line))
    padded = line + " " * max(state.last_width - width, 0)
    state.last_width = width
    return padded


def _format_line(indent: int, msg: str, symbol: str) -> str:
    return f"{'  ' * indent}{symbol} {msg}"


def _format_progress_symbol(done: int, total: int) -> str:
    width = len(str(total))
    return f"{done:>{width}}/{total}"


# flush-right time: cursor-forward 999 clamps at the last column, then
# back up by the visible length — measured before painting, since the
# colour escapes occupy zero columns; off-tty (logs) plain text only
def _format_close_line(is_tty: bool, line: str, elapsed: str) -> str:
    if is_tty:
        return (
            f"{line}\x1b[999C\x1b[{len(elapsed) - 1}D{_paint(elapsed, blue)}"
        )
    return f"{line} {elapsed}"


def _paint_symbol(text: str, colour: str) -> str:
    return _paint(f"[{text}]", colour)


def _paint(text: str, colour: str) -> str:
    return f"{colour}{text}{normal}"
