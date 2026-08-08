"""E2E coverage of the language toggle (hotkey L).

The language lives in localStorage and is applied through a full page
reload: text.js reads the key before anything renders and stamps
<html lang>, so the assertions cover the persisted key, the document
language, a translated control, and the French month names on a chart
axis (the frenchLocale wiring in plot.js).
"""

import re

from playwright.sync_api import Page, expect

from tests.e2e.drivers import (
    goto_app,
    select_station,
    set_period,
    wait_chart,
)

pikauba_amont = "061022"

# abbreviations distinct from the English ones, so a match proves the
# French locale drew the axis
french_month_re = re.compile(r"fév|avr|aoû|déc")

#### tests ####


def test_language_toggle_translates_and_persists(
    page: Page, base_url: str
) -> None:
    goto_app(page)
    expect(page.locator("html")).to_have_attribute("lang", "en-CA")
    station_label = page.locator("#controls .controls__field > span").first
    expect(station_label).to_have_text("Calibration station")

    # the toggle writes localStorage and reloads; the new document is
    # French before anything renders
    page.keyboard.press("L")
    expect(page.locator("html")).to_have_attribute("lang", "fr-CA")
    assert (
        page.evaluate(
            "window.localStorage.getItem('holmes--settings--language')"
        )
        == "fr"
    )
    goto_app(page)
    expect(station_label).to_have_text("Station de calage")

    # a one-year window draws month ticks, which must come from the
    # French d3 locale
    select_station(page, "calibration", pikauba_amont)
    set_period(page, "calibration", "1980-01-01", "1980-12-31")
    wait_chart(page, "hydrographs__calibration", timeout=60_000)
    ticks = page.locator("#hydrographs__calibration-svg .x-axis text")
    expect(ticks.filter(has_text=french_month_re).first).to_be_attached()

    # the hotkey is ignored while an input has focus, so blur first
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.keyboard.press("L")
    expect(page.locator("html")).to_have_attribute("lang", "en-CA")
    assert (
        page.evaluate(
            "window.localStorage.getItem('holmes--settings--language')"
        )
        == "en"
    )
