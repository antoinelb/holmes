"""E2E coverage of the missing-basemap notice.

A pyramid tile the server cannot find answers 404 (a broken or outdated
data archive); the map must then show a persistent notice naming the
first failing tile instead of silently drawing black squares. The 404 is
simulated by routing, so the warmed data directory stays intact.
"""

from playwright.sync_api import Page, Route, expect

from tests.e2e.drivers import goto_app

#### tests ####


def test_missing_tiles_show_the_notice(page: Page, base_url: str) -> None:
    page.route("**/map/**", fail_tile)
    goto_app(page)
    notice = page.locator("#map__notice")
    expect(notice).to_be_visible()
    expect(notice).to_contain_text("data archive")
    expect(notice.locator("code")).to_contain_text("/map/")
    # the notice shares the legend's centred corner: in flow it would widen
    # it and push the legend sideways
    shown = legend_x(page)
    notice.evaluate("node => { node.hidden = true; }")
    assert legend_x(page) == shown


def test_served_tiles_keep_the_notice_hidden(
    page: Page, base_url: str
) -> None:
    goto_app(page)
    expect(page.locator("#map .leaflet-tile-loaded").first).to_be_visible()
    expect(page.locator("#map__notice")).to_be_hidden()


#### shared helpers ####


def fail_tile(route: Route) -> None:
    route.fulfill(status=404, body="missing")


def legend_x(page: Page) -> float:
    box = page.locator("#map__legend").bounding_box()
    assert box is not None
    return box["x"]
