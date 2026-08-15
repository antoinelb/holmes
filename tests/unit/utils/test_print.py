import sys
import threading

import pytest

import holmes.utils.print as print_
from holmes.utils.print import (
    done_print,
    fail_print,
    progress_task,
    task,
    warn_print,
)


@pytest.fixture
def state(request, monkeypatch):
    mode = getattr(request, "param", "plain")
    state = print_._PrintState(mode=mode)
    monkeypatch.setattr(print_, "_state", state)
    return state


def _strip(text):
    return print_._colour.sub("", text)


class TestDetectMode:
    def test_tty(self, monkeypatch):
        fake = type("FakeTty", (), {"isatty": lambda self: True})()
        monkeypatch.setattr(sys, "stdout", fake)
        assert print_._detect_mode() == "tty"

    def test_notebook(self, monkeypatch):
        out_stream = type("OutStream", (), {"isatty": lambda self: False})
        out_stream.__module__ = "ipykernel.iostream"
        monkeypatch.setattr(sys, "stdout", out_stream())
        assert print_._detect_mode() == "notebook"

    def test_plain(self, capsys):
        # capsys' replacement stdout is neither a tty nor ipykernel's
        assert print_._detect_mode() == "plain"


class TestTask:
    def test_plain_prints_only_the_close_line(self, state, capsys):
        with task("Doing...", "Done."):
            pass
        raw = capsys.readouterr().out
        out = _strip(raw)
        assert "Doing..." not in out
        assert "\r" not in raw
        assert print_.erase_line not in raw
        assert out.startswith("[+] Done. [0.")
        assert out.endswith("s]\n")

    def test_nested_tasks_indent_and_materialize_parent(self, state, capsys):
        with task("Outer...", "Outer done."):
            with task("Inner...", "Inner done."):
                pass
        out = _strip(capsys.readouterr().out)
        lines = out.splitlines()
        assert lines[0] == "[→] Outer..."
        assert lines[1].startswith("  [+] Inner done. [0.")
        assert lines[2].startswith("[+] Outer done. [0.")

    def test_exception_closes_with_original_msg(self, state, capsys):
        with pytest.raises(ValueError):
            with task("Doing...", "Done."):
                raise ValueError("boom")
        out = _strip(capsys.readouterr().out)
        assert out.startswith("[x] Doing... [0.")
        assert "Done." not in out

    def test_done_with_replaces_the_closing_message(self, state, capsys):
        with task("Doing...", "Done.") as t:
            t.done_with("Did 3 things.")
        out = _strip(capsys.readouterr().out)
        assert "Did 3 things." in out
        assert "Done." not in out

    def test_closing_out_of_order_keeps_the_other_pending(self, state, capsys):
        a = task("A...", "A done.")
        b = task("B...", "B done.")
        a.__exit__(None, None, None)
        b.__exit__(None, None, None)
        out = _strip(capsys.readouterr().out)
        assert "[→] A..." in out
        assert "[+] A done." in out
        assert "[+] B done." in out

    def test_increment_without_progress_is_a_no_op(self, state, capsys):
        with task("Doing...", "Done.") as t:
            t.increment()
        assert state.progress is None

    def test_indent_never_goes_negative(self, state):
        with task("Doing...", "Done."):
            pass
        with task("Again...", "Done again."):
            pass
        assert state.indent == 0


@pytest.mark.parametrize("state", ["tty"], indirect=True)
class TestTaskTty:
    def test_transient_line_is_drawn_and_erased(self, state, capsys):
        with task("Doing...", "Done."):
            pass
        out = capsys.readouterr().out
        assert out.startswith(print_.erase_line)
        assert "[∗] Doing..." in _strip(out)
        assert "[+] Done." in _strip(out)

    def test_close_line_flushes_elapsed_right(self, state, capsys):
        with task("Doing...", "Done."):
            pass
        out = capsys.readouterr().out
        assert "\x1b[999C" in out
        assert "\x1b[5D" in out

    def test_permanent_with_no_bottom_line_ends_clean(self, state, capsys):
        done_print("Standalone.")
        out = capsys.readouterr().out
        assert out.startswith(print_.erase_line)
        assert out.endswith(" Standalone.\n")


@pytest.mark.parametrize("state", ["notebook"], indirect=True)
class TestTaskNotebook:
    def test_rewrites_with_carriage_return(self, state, capsys):
        with task("Doing...", "Done."):
            pass
        out = capsys.readouterr().out
        assert out.startswith("\r")
        assert print_.erase_line not in out

    def test_pads_a_shorter_line_to_cover_the_previous_one(
        self, state, capsys
    ):
        with task("A much longer transient message", "ok"):
            pass
        out = _strip(capsys.readouterr().out)
        open_line, close_line = out.split("\n")[0].split("\r")[1:]
        assert open_line == "[∗] A much longer transient message"
        assert len(close_line) == len(open_line)
        assert close_line.rstrip().startswith("[+] ok [0.")


class TestProgressTask:
    def test_increment_advances_the_counter(self, state, capsys):
        with progress_task("Working...", "Worked.", total=120) as t:
            t.increment()
        assert state.progress is None
        out = _strip(capsys.readouterr().out)
        assert out.startswith("[+] Worked. [0.")

    def test_counter_is_right_aligned_to_the_total_width(self, state, capsys):
        state.mode = "tty"
        with progress_task("Working...", "Worked.", total=120) as t:
            t.increment()
            t.increment()
            t.increment()
        out = _strip(capsys.readouterr().out)
        assert "[  0/120] Working..." in out
        assert "[  3/120] Working..." in out

    def test_nested_task_shows_counter_below_it(self, state, capsys):
        state.mode = "tty"
        with progress_task("Working...", "Worked.", total=2) as t:
            warn_print("Careful.")
            t.increment()
        out = _strip(capsys.readouterr().out)
        # the pending line materialized, leaving the counter alone below
        assert "[→] Working..." in out
        assert "  [1/2] Working..." in out

    def test_second_progress_task_warns_and_is_uncounted(self, state, capsys):
        with progress_task("Outer...", "Outer done.", total=2) as outer:
            with progress_task("Inner...", "Inner done.", total=9) as inner:
                inner.increment()
            assert state.progress is not None
            assert state.progress.id == outer.id
            assert state.progress.done == 0
        out = _strip(capsys.readouterr().out)
        assert "A progress task already exists." in out

    def test_increment_is_thread_safe(self, state):
        with progress_task("Working...", "Worked.", total=80) as t:
            threads = [
                threading.Thread(
                    target=lambda: [t.increment() for _ in range(10)]
                )
                for _ in range(8)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            assert state.progress is not None
            assert state.progress.done == 80


class TestDonePrint:
    def test_prints_a_permanent_green_line(self, state, capsys):
        done_print("Done.")
        out = capsys.readouterr().out
        assert print_.bold_green in out
        assert _strip(out) == "[+] Done.\n"


class TestWarnPrint:
    def test_prints_a_permanent_yellow_line(self, state, capsys):
        warn_print("Careful.")
        out = capsys.readouterr().out
        assert print_.bold_yellow in out
        assert _strip(out) == "[!] Careful.\n"


class TestFailPrint:
    def test_prints_a_permanent_red_line(self, state, capsys):
        fail_print("Broken.")
        out = capsys.readouterr().out
        assert print_.bold_red in out
        assert _strip(out) == "[x] Broken.\n"

    def test_swallows_a_broken_stream(self, state, monkeypatch):
        def broken_write(text):
            raise OSError("broken pipe")

        fake = type(
            "FakeOut",
            (),
            {
                "write": staticmethod(broken_write),
                "flush": staticmethod(lambda: None),
            },
        )()
        monkeypatch.setattr(sys, "stdout", fake)
        fail_print("Broken.")
