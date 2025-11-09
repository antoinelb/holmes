"""Tests for src/utils/plotting.py - plotting utilities."""

import plotly.graph_objects as go
from src.utils import plotting


# Test colours


def test_colours_is_list():
    """Colours should be a list."""
    assert isinstance(plotting.colours, list)


def test_colours_not_empty():
    """Colours list should not be empty."""
    assert len(plotting.colours) > 0


def test_colours_are_strings():
    """All colours should be strings."""
    assert all(isinstance(c, str) for c in plotting.colours)


def test_colours_are_hex():
    """All colours should be hex color codes."""
    for colour in plotting.colours:
        assert colour.startswith("#")
        assert len(colour) == 7  # #RRGGBB


# Test template


def test_template_is_dict():
    """Template should be a dict."""
    assert isinstance(plotting.template, dict)


def test_template_has_layout():
    """Template should have layout key."""
    assert "layout" in plotting.template


def test_template_layout_is_plotly_layout():
    """Template layout should be a plotly Layout."""
    assert isinstance(plotting.template["layout"], go.Layout)


# Test convert_colour


def test_convert_colour_default_opacity():
    """Convert hex to rgba with default opacity."""
    result = plotting.convert_colour("#fd7f6f")
    assert result == "rgba(253,127,111,1)"


def test_convert_colour_custom_opacity():
    """Convert hex to rgba with custom opacity."""
    result = plotting.convert_colour("#fd7f6f", opacity=0.5)
    assert result == "rgba(253,127,111,0.5)"


def test_convert_colour_zero_opacity():
    """Convert hex to rgba with zero opacity."""
    result = plotting.convert_colour("#000000", opacity=0)
    assert result == "rgba(0,0,0,0)"


def test_convert_colour_full_opacity():
    """Convert hex to rgba with full opacity."""
    result = plotting.convert_colour("#ffffff", opacity=1.0)
    assert result == "rgba(255,255,255,1.0)"


def test_convert_colour_without_hash():
    """Should handle color without # prefix."""
    # The function strips the #, so it should work with or without
    result = plotting.convert_colour("fd7f6f")
    assert result == "rgba(253,127,111,1)"


# Test compute_domain


def test_compute_domain_returns_tuple():
    """compute_domain should return (start, end) tuple."""
    result = plotting.compute_domain(0, 3, 0.1)
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_compute_domain_values_between_zero_and_one():
    """Domain values should be between 0 and 1."""
    start, end = plotting.compute_domain(0, 3, 0.1)
    assert 0 <= start < end <= 1


def test_compute_domain_first_starts_at_zero():
    """First domain should start at or near 0."""
    start, end = plotting.compute_domain(0, 3, 0.1)
    assert start == 0.0


def test_compute_domain_last_ends_at_one():
    """Last domain should end at or near 1."""
    start, end = plotting.compute_domain(2, 3, 0.1)
    assert end <= 1.0  # Should be at or near 1


def test_compute_domain_no_padding():
    """With no padding, domains should span entire range."""
    # First domain
    start1, end1 = plotting.compute_domain(0, 3, 0.0)
    assert start1 == 0.0

    # Middle domain
    start2, end2 = plotting.compute_domain(1, 3, 0.0)
    assert start2 > end1 or start2 == end1


def test_compute_domain_multiple_items():
    """compute_domain should work for multiple items."""
    n = 5
    pad = 0.05
    domains = [plotting.compute_domain(i, n, pad) for i in range(n)]

    # All should be valid
    for start, end in domains:
        assert 0 <= start < end <= 1

    # Should be in order
    for i in range(len(domains) - 1):
        assert domains[i][1] <= domains[i + 1][0]


def test_compute_domain_reverse_false():
    """Normal order should give increasing domains."""
    start0, end0 = plotting.compute_domain(0, 3, 0.1, reverse=False)
    start1, end1 = plotting.compute_domain(1, 3, 0.1, reverse=False)

    assert start0 < start1


def test_compute_domain_reverse_true():
    """Reversed order should give decreasing domains."""
    start0, end0 = plotting.compute_domain(0, 3, 0.1, reverse=True)
    start1, end1 = plotting.compute_domain(1, 3, 0.1, reverse=True)

    assert start0 > start1


def test_compute_domain_single_item():
    """Single item should span most of the range."""
    start, end = plotting.compute_domain(0, 1, 0.0)
    assert start == 0.0
    assert end == 1.0


def test_compute_domain_equal_widths():
    """All domains with same n and pad should have equal width."""
    n = 4
    pad = 0.1
    domains = [plotting.compute_domain(i, n, pad) for i in range(n)]
    widths = [end - start for start, end in domains]

    # All widths should be approximately equal
    for width in widths[1:]:
        assert abs(width - widths[0]) < 1e-10
