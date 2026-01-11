"""Unit tests for holmes.utils.print module."""

from hypothesis import given, settings
from hypothesis import strategies as st

from holmes.utils.print import format_list


class TestFormatList:
    """Tests for format_list function."""

    def test_format_list_empty(self):
        """Empty list returns empty string."""
        assert format_list([]) == ""

    def test_format_list_single(self):
        """Single item returns item."""
        assert format_list(["one"]) == "one"

    def test_format_list_two_items(self):
        """Two items joined with 'and'."""
        assert format_list(["one", "two"]) == "one and two"

    def test_format_list_three_items(self):
        """Three items joined with comma and 'and'."""
        assert format_list(["one", "two", "three"]) == "one, two and three"

    def test_format_list_with_or(self):
        """Items can be joined with 'or'."""
        assert (
            format_list(["one", "two", "three"], word="or")
            == "one, two or three"
        )

    def test_format_list_with_surround(self):
        """Items can be surrounded with a character."""
        assert format_list(["a", "b"], surround="`") == "`a` and `b`"

    def test_format_list_tuple_input(self):
        """Tuple input works the same as list."""
        assert format_list(("one", "two")) == "one and two"

    def test_format_list_surround_and_or(self):
        """Surround and 'or' can be combined."""
        result = format_list(["x", "y", "z"], surround="'", word="or")
        assert result == "'x', 'y' or 'z'"


class TestHypothesis:
    """Property-based tests for format_list."""

    @given(st.lists(st.text(min_size=1, max_size=10), min_size=0, max_size=10))
    @settings(max_examples=50)
    def test_empty_output_only_for_empty_input(self, items):
        """Output is empty only if input is empty."""
        result = format_list(items)
        if len(items) == 0:
            assert result == ""
        else:
            assert result != ""

    @given(st.lists(st.text(min_size=1, max_size=5), min_size=2, max_size=10))
    @settings(max_examples=50)
    def test_all_items_present_in_output(self, items):
        """All items appear in the output."""
        result = format_list(items)
        for item in items:
            assert item in result

    @given(st.lists(st.text(min_size=1, max_size=5), min_size=1, max_size=1))
    @settings(max_examples=20)
    def test_single_item_equals_output(self, items):
        """Single item output equals the item."""
        result = format_list(items)
        assert result == items[0]

    @given(st.lists(st.text(min_size=1, max_size=5), min_size=2, max_size=10))
    @settings(max_examples=50)
    def test_and_appears_in_multi_item_output(self, items):
        """'and' appears in multi-item output."""
        result = format_list(items, word="and")
        assert " and " in result

    @given(st.lists(st.text(min_size=1, max_size=5), min_size=2, max_size=10))
    @settings(max_examples=50)
    def test_or_appears_when_specified(self, items):
        """'or' appears when specified."""
        result = format_list(items, word="or")
        assert " or " in result
