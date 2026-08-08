"""E2E coverage of the theme toggle (hotkey T).

The light theme is a `light` class on <body>; the basemap always serves
dark tiles, so light mode relies on the CSS inversion filter on the
Leaflet tile pane (map.css) — asserted here so the rule cannot silently
disappear.
"""

import re

from playwright.sync_api import Page, expect

light_re = re.compile(r"light")

#### tests ####


def test_theme_toggle_flips_body_and_map_tiles(
    page: Page, base_url: str
) -> None:
    page.goto("/")
    # the map (and its tile pane) is created lazily by the stations step
    tile_pane = page.locator("#map .leaflet-tile-pane")
    expect(tile_pane).to_be_attached()
    expect(page.locator("body")).not_to_have_class(light_re)
    assert tile_filter(page) == "none"

    page.keyboard.press("T")
    expect(page.locator("body")).to_have_class(light_re)
    assert tile_filter(page) != "none"

    page.keyboard.press("T")
    expect(page.locator("body")).not_to_have_class(light_re)
    assert tile_filter(page) == "none"


#### shared helpers ####


def tile_filter(page: Page) -> str:
    return page.locator("#map .leaflet-tile-pane").evaluate(
        "(el) => getComputedStyle(el).filter"
    )
