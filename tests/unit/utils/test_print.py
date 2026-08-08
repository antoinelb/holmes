from holmes.utils.print import done_print, load_print, load_progress


class TestLoadPrint:
    def test_prints_text(self, capsys):
        load_print("Loading...", indent=2)
        out = capsys.readouterr().out
        assert "Loading..." in out
        assert out.endswith("\r")

    def test_echo_false_prints_nothing(self, capsys):
        load_print("Loading...", echo=False)
        assert capsys.readouterr().out == ""


class TestDonePrint:
    def test_prints_text(self, capsys):
        done_print("Done.")
        out = capsys.readouterr().out
        assert "Done." in out
        assert out.endswith("\n")

    def test_echo_false_prints_nothing(self, capsys):
        done_print("Done.", echo=False)
        assert capsys.readouterr().out == ""


class TestLoadProgress:
    def test_echo_false_passes_through(self, capsys):
        assert list(load_progress([1, 2, 3], "Working...", echo=False)) == [
            1,
            2,
            3,
        ]
        assert capsys.readouterr().out == ""

    def test_sized_iterable_shows_total(self, capsys):
        assert list(load_progress([1, 2, 3], "Working...")) == [1, 2, 3]
        out = capsys.readouterr().out
        assert "1/3" in out
        assert "3/3" in out

    def test_explicit_total_wins_over_len(self, capsys):
        items = load_progress((x for x in [1, 2]), "Working...", total=5)
        assert list(items) == [1, 2]
        assert "2/5" in capsys.readouterr().out

    def test_unsized_iterator_counts_without_total(self, capsys):
        items = load_progress((x for x in [1, 2]), "Working...")
        assert list(items) == [1, 2]
        out = capsys.readouterr().out
        assert "[2]" in out
        assert "/" not in out
