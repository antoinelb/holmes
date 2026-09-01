"""E2E coverage of the projection step's indicators chart.

The chart is the only one whose reference ticks are raised after every
draw, which is how its legend swatches once ended up outside the SVG:
they carry the same `series-tick` class as the data ticks. The legend
assertion below is the regression guard for that.
"""

from playwright.sync_api import Page, expect

from tests.e2e.drivers import (
    digit_re,
    goto_app,
    goto_step,
    select_station,
    select_weather_method,
    set_calibration_settings,
    set_model_config,
    set_period,
    wait_chart,
)

pikauba_amont = "061022"

# one hydro model over the ClimEx ensemble draws in about a second, but a
# cold product read is far slower; same margin the screenshot script uses
projection_timeout = 180_000

indicator_labels = ["Winter min", "Spring max", "Summer min", "Autumn max"]

#### tests ####


def test_indicators_chart(page: Page, base_url: str) -> None:
    goto_projection(page)

    svg = page.locator("#projection__indicators-svg")
    # the two legend swatches must stay inside their translated row group:
    # reparenting them to the SVG root drops the transform and drags them
    # off-canvas, leaving the labels stranded without their lines
    assert svg.locator("g.legend line").count() == 2
    # the ensemble median and the historical reference, one per column
    assert svg.locator(":scope > line.series-tick").count() == 8

    # text_content, not inner_text: an SVG <text> has no innerText
    labels = svg.locator("text.dot-profile-label")
    assert labels.all_text_contents() == indicator_labels

    # the unit moved from the figcaption to the y-axis title, whose name and
    # units are separate tspans
    title = svg.locator("text.axis-title")
    assert title.text_content() == "Indicators(mm/day)"
    assert page.locator("#projection__indicators figcaption").count() == 0


#### helpers ####


def goto_projection(page: Page) -> None:
    # projection only `uses` config keys, so it unlocks as soon as the
    # calibration provides params; the simulation step is not on the path
    goto_app(page)
    select_station(page, "calibration", pikauba_amont)
    set_period(page, "calibration", "1980-01-01", "1984-12-31")
    select_station(page, "simulation", pikauba_amont)
    set_period(page, "simulation", "1985-01-01", "1989-12-31")

    goto_step(page, "Weather")
    select_weather_method(page, "nearest_stations")

    goto_step(page, "Model")
    set_model_config(page, "single", ["gr4j"], "cemaneige")

    goto_step(page, "Calibration")
    wait_chart(page, "calibration__streamflow", timeout=120_000)
    # manual: the entry auto-simulate fills params without an SCE run
    set_calibration_settings(page, "rmse", "none", "manual")
    expect(page.locator("#calibration__chip-gr4j")).to_have_text(
        digit_re, timeout=120_000
    )

    goto_step(page, "Projection")
    wait_chart(page, "projection__indicators", timeout=projection_timeout)
