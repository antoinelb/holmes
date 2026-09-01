"""E2E coverage of the projection step's two charts.

The indicators chart is the only one whose reference ticks are raised
after every draw, which is how its legend swatches once ended up outside
the SVG: they carry the same `series-tick` class as the data ticks. The
legend assertion below is the regression guard for that.

Its y scale is also broken into two segments, and the guard for that is
`test_indicators_split_scale`: the previous scale broke the *domain* but
gave both segments the same slope, so it rendered as one linear axis and
the low-flow columns kept no visible spread.
"""

import re

from playwright.sync_api import Locator, Page, expect

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


def test_indicators_split_scale(page: Page, base_url: str) -> None:
    goto_projection(page)

    svg = page.locator("#projection__indicators-svg")
    # the glyph marks the break; everything else is read relative to it
    breaks = svg.locator("line.axis-break")
    assert breaks.count() == 2
    middle = sum(attribute_values(breaks, "y1")) / 2

    ticks = axis_ticks(svg.locator("g.y-axis"))
    low = [tick for tick in ticks if tick[1] > middle]
    high = [tick for tick in ticks if tick[1] < middle]
    assert len(low) >= 2, ticks
    assert len(high) >= 2, ticks

    # the point of the break: the two halves must not share a slope, or the
    # minima stay crushed under the freshet as they were before
    assert band_slope(low) > 2 * band_slope(high), (low, high)

    # and the break is a band of whitespace, not a hairline: nothing is drawn
    # within 5 px either side of it
    for selector, attribute in (
        ("line.grid-horizontal", "y1"),
        ("circle.series-point--member", "cy"),
        (":scope > line.series-tick", "y1"),
        ("g.y-axis g.tick text", None),
    ):
        marks = (
            [tick[1] for tick in ticks]
            if attribute is None
            else attribute_values(svg.locator(selector), attribute)
        )
        for value in marks:
            assert abs(value - middle) >= 5, (selector, value, middle)


def test_regime_month_labels_clear_the_y_axis(
    page: Page, base_url: str
) -> None:
    goto_projection(page)

    svg = page.locator("#projection__regime-svg")
    # "Jan" is centred on the y axis, where the 0 tick is pinned to the
    # baseline; the month row has to sit below it rather than through it
    jan_text = svg.locator("g.x-axis g.tick text").first
    zero_text = svg.locator("g.y-axis g.tick text").first
    assert zero_text.text_content() == "0"
    jan = jan_text.bounding_box()
    zero = zero_text.bounding_box()
    assert jan is not None and zero is not None
    assert jan["y"] >= zero["y"] + zero["height"], (jan, zero)
    # and the labels stay inside the SVG rather than clipping on the descender
    plot = svg.bounding_box()
    assert plot is not None
    assert jan["y"] + jan["height"] <= plot["y"] + plot["height"], (jan, plot)


#### helpers ####


# [(value, y)] sorted by value; d3 positions each tick group with a
# translate, which keeps everything in the SVG's own units
def axis_ticks(axis: Locator) -> list[tuple[float, float]]:
    ticks = []
    for tick in axis.locator("g.tick").all():
        transform = tick.get_attribute("transform") or ""
        match = re.search(r"translate\(([^,]+),\s*([^)]+)\)", transform)
        assert match, transform
        text = tick.locator("text").text_content()
        assert text
        ticks.append((float(text), float(match.group(2))))
    return sorted(ticks)


def band_slope(band: list[tuple[float, float]]) -> float:
    return (band[0][1] - band[-1][1]) / (band[-1][0] - band[0][0])


def attribute_values(locator: Locator, attribute: str) -> list[float]:
    return [
        float(element.get_attribute(attribute) or "nan")
        for element in locator.all()
    ]


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
