"""Tests for src/utils/print.py - print utilities."""

from holmes.utils import print as print_utils


# Test format_list


def test_format_list_empty():
    """Empty list should return empty string."""
    result = print_utils.format_list([])
    assert result == ""


def test_format_list_single_item():
    """Single item should return just that item."""
    result = print_utils.format_list(["apple"])
    assert result == "apple"


def test_format_list_two_items():
    """Two items should be joined with 'and'."""
    result = print_utils.format_list(["apple", "banana"])
    assert result == "apple and banana"


def test_format_list_multiple_items():
    """Multiple items should use commas and 'and'."""
    result = print_utils.format_list(["apple", "banana", "cherry"])
    assert result == "apple, banana and cherry"


def test_format_list_with_or():
    """Should use 'or' when specified."""
    result = print_utils.format_list(["apple", "banana"], word="or")
    assert result == "apple or banana"


def test_format_list_multiple_with_or():
    """Multiple items should use 'or'."""
    result = print_utils.format_list(["apple", "banana", "cherry"], word="or")
    assert result == "apple, banana or cherry"


def test_format_list_with_surround():
    """Should surround each item."""
    result = print_utils.format_list(["apple", "banana"], surround="'")
    assert result == "'apple' and 'banana'"


def test_format_list_with_quotes():
    """Should surround items with quotes."""
    result = print_utils.format_list(["apple", "banana", "cherry"], surround='"')
    assert result == '"apple", "banana" and "cherry"'


def test_format_list_with_brackets():
    """Should work with other surround characters."""
    result = print_utils.format_list(["a", "b"], surround="[")
    assert result == "[a[ and [b["


def test_format_list_tuple_input():
    """Should work with tuple input."""
    result = print_utils.format_list(("apple", "banana"))
    assert result == "apple and banana"


def test_format_list_four_items():
    """Four items should format correctly."""
    result = print_utils.format_list(["a", "b", "c", "d"])
    assert result == "a, b, c and d"


def test_format_list_with_surround_and_or():
    """Should work with both surround and 'or'."""
    result = print_utils.format_list(["apple", "banana"], surround="'", word="or")
    assert result == "'apple' or 'banana'"


def test_format_list_empty_surround():
    """Empty surround should be same as no surround."""
    result1 = print_utils.format_list(["apple", "banana"], surround="")
    result2 = print_utils.format_list(["apple", "banana"])
    assert result1 == result2


def test_format_list_with_spaces():
    """Should preserve spaces in items."""
    result = print_utils.format_list(["hello world", "foo bar"])
    assert result == "hello world and foo bar"
