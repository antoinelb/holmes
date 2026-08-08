"""Regenerate the documentation screenshots in docs/assets/images/.

Walks the pipeline once in a single browser session against a local
server (warm data/ assumed) and shoots every scene twice, dark then
light theme, as <scene>-{dark,light}.png. Run via `make screenshots`.

Manual slider moves pick deterministic targets and SCE runs on its
default seed, so regenerated images should only churn where the UI
itself changed.
"""

import re
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import Download, Page, expect, sync_playwright

root_dir = Path(__file__).parents[1]
sys.path.insert(0, str(root_dir))

from tests.e2e import drivers  # noqa: E402

shots_dir = root_dir / "docs" / "assets" / "images" / "screenshots"

pikauba_amont = "061022"
pikauba_aval = "061028"
aux_ecorces = "061020"

sce_max_evaluations = 500

light_re = re.compile(r"light")


def main() -> None:
    shots_dir.mkdir(parents=True, exist_ok=True)
    with drivers.run_server() as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            base_url=url,
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            reduced_motion="reduce",
        )
        page = context.new_page()
        page.set_default_timeout(30_000)
        drivers.goto_app(page)
        shoot(page, "app-start")
        scene_map_dialog(page)
        scene_stations(page)
        scene_weather(page)
        scene_model_single(page)
        scene_calibration_manual(page)
        scene_ensemble_sce(page)
        scene_simulation(page)
        scene_projection(page)
        scene_settings(page)
        scene_import_dialog(page)
        browser.close()


#### scenes ####


def scene_map_dialog(page: Page) -> None:
    # shot before any selection so the hydrograph panel does not overlap
    # the bottom of the map and the card shows both role buttons; the
    # topmost marker keeps the card fully over the map. events are
    # dispatched because a marker may sit under other panes
    markers = page.locator(".map__marker")
    topmost = min(
        (marker for marker in markers.all()),
        key=lambda marker: (marker.bounding_box() or {"y": 1e9})["y"],
    )
    topmost.dispatch_event("click")
    dialog = page.locator("#map__dialog")
    expect(dialog).to_be_visible()
    shoot(page, "stations-map-dialog", clip="#map")
    # leaflet closes the card on a map background click
    page.locator("#map").dispatch_event("click")
    expect(dialog).to_be_hidden()


def scene_stations(page: Page) -> None:
    # the tp2 split-sample setup: calibrate 1980-1989, validate 1990-1999
    drivers.select_station(page, "calibration", pikauba_amont)
    drivers.set_period(page, "calibration", "1980-01-01", "1989-12-31")
    drivers.select_station(page, "simulation", pikauba_amont)
    drivers.set_period(page, "simulation", "1990-01-01", "1999-12-31")
    drivers.wait_chart(page, "hydrographs__calibration", timeout=60_000)
    drivers.wait_chart(page, "hydrographs__simulation", timeout=60_000)
    shoot(page, "stations-controls", clip="#controls")
    shoot(page, "stations-overview")
    shoot(page, "stations-hydrographs", clip="#hydrographs")
    # the map stays on its default centre, north of the watersheds; pan
    # so the selected station and its weather sources (centroid links,
    # era5 and ministry-grid cells) are framed for the weather scenes —
    # the map persists across steps, so weather inherits the framing
    pan_map(page, target_x=620, target_y=320)


def scene_weather(page: Page) -> None:
    drivers.goto_step(page, "Weather")
    shoot(page, "weather-methods", clip="#controls")
    # hovering the station draws its watershed over the method's cells
    # or centroid links; end on nearest_stations, the method the rest of
    # the walk uses
    marker = ".map__marker--calibration"
    drivers.select_weather_method(page, "era5")
    shoot(page, "weather-era5", hover=marker)
    drivers.select_weather_method(page, "ministry_grid")
    shoot(page, "weather-ministry-grid", hover=marker)
    drivers.select_weather_method(page, "nearest_stations")
    shoot(page, "weather-nearest-stations", hover=marker)


def scene_model_single(page: Page) -> None:
    drivers.goto_step(page, "Model")
    drivers.set_model_config(page, "single", ["gr4j"], "cemaneige")
    # populate the sticky detail panel before the mouse is parked
    page.locator("#model__option-hydro-gr4j").hover()
    expect(page.locator("#model__detail .model__detail-title")).to_be_visible()
    shoot(page, "model-single")


def scene_calibration_manual(page: Page) -> None:
    drivers.goto_step(page, "Calibration")
    drivers.wait_chart(page, "calibration__streamflow", timeout=120_000)
    drivers.set_calibration_settings(page, "rmse", "none", "manual")
    expect(page.locator("#calibration__chip-gr4j")).to_have_text(
        drivers.digit_re, timeout=120_000
    )
    # one slider move so the simulated line diverges from the defaults
    drivers.set_param_slider(page, "gr4j", 0)
    shoot(page, "calibration-overview")
    shoot(
        page,
        "calibration-sliders",
        clip="details.calibration__model[data-model='gr4j']",
    )
    shoot(page, "calibration-streamflow", clip="#calibration__streamflow")
    brush_zoom(page)
    shoot(page, "calibration-brush-zoom", clip="#calibration__streamflow")
    reset_zoom(page)
    shoot(page, "sidebar-pipeline", clip="#sidebar")


def scene_ensemble_sce(page: Page) -> None:
    drivers.goto_step(page, "Model")
    drivers.set_model_config(page, "ensemble", ["gr4j", "bucket"], "cemaneige")
    shoot(page, "model-ensemble")
    drivers.goto_step(page, "Calibration")
    drivers.wait_chart(page, "calibration__streamflow", timeout=120_000)
    drivers.set_calibration_settings(page, "rmse", "none", "sce")
    drivers.set_algo_param(page, "max_evaluations", sce_max_evaluations)
    shoot(page, "calibration-sce-settings", clip="#controls")
    drivers.run_sce(page, ["gr4j", "bucket"])
    # fold the algorithm settings back so the per-model sections and
    # their objective chips fit in the card's scroll area
    close_details(
        page, "details.controls__details:has(#calibration__algo-params)"
    )
    shoot(page, "calibration-sce-result")
    shoot(page, "calibration-objective", clip="#calibration__objective")


def scene_simulation(page: Page) -> None:
    drivers.goto_step(page, "Simulation")
    drivers.assert_simulation_metrics(page, ["gr4j", "bucket"])
    shoot(page, "simulation-overview")
    shoot(page, "simulation-metrics", clip="#simulation__metrics")


def scene_projection(page: Page) -> None:
    drivers.goto_step(page, "Projection")
    drivers.wait_chart(page, "projection__regime", timeout=180_000)
    drivers.wait_chart(page, "projection__indicators", timeout=180_000)
    shoot(page, "projection-overview")
    shoot(page, "projection-controls", clip="#controls")
    # a redraw changes the signature; waiting on the loading class alone
    # would race the fetch start
    svg = page.locator("#projection__regime-svg")
    signature = svg.get_attribute("data-signature") or ""
    page.locator("#projection__climate-model").select_option("ESPO-G6-R2")
    scenario = "#projection__scenario button[data-value='ssp3-7.0']"
    page.locator(scenario).click()
    horizon = "#projection__horizon button[data-value='2070-2099']"
    page.locator(horizon).click()
    expect(svg).not_to_have_attribute(
        "data-signature", signature, timeout=180_000
    )
    drivers.wait_chart(page, "projection__regime", timeout=180_000)
    drivers.wait_chart(page, "projection__indicators", timeout=180_000)
    shoot(page, "projection-variant")


def scene_settings(page: Page) -> None:
    page.locator("#settings > button").click()
    expect(page.locator("#settings")).to_have_class(re.compile(r"--open"))
    shoot(page, "settings-panel", clip="#settings")
    page.keyboard.press("Escape")


def scene_import_dialog(page: Page) -> None:
    # last scene: it churns the calibration bench. export the current
    # fit, switch context, then import the file back to raise the
    # config-diff dialog
    drivers.goto_step(page, "Calibration")
    with tempfile.TemporaryDirectory() as tmp:
        exports = export_files(page, "#calibration__export", Path(tmp), 2)
        exported = next(p for p in exports if p.suffix == ".json")
        drivers.goto_step(page, "Stations")
        drivers.select_station(page, "calibration", aux_ecorces)
        drivers.set_period(page, "calibration", "2010-01-01", "2019-12-31")
        drivers.goto_step(page, "Calibration")
        drivers.wait_chart(page, "calibration__streamflow", timeout=120_000)
        with page.expect_file_chooser() as chooser_info:
            page.locator("#calibration__import").click()
        chooser_info.value.set_files(exported)
    dialog = page.locator("#calibration__import-dialog")
    expect(dialog).to_be_visible()
    shoot(page, "calibration-import-dialog")
    dialog.get_by_role("button", name="Cancel").click()
    expect(dialog).to_be_hidden()


#### helpers ####


def shoot(
    page: Page,
    name: str,
    clip: str | None = None,
    hover: str | None = None,
) -> None:
    settle(page)
    if hover:
        # e.g. hovering a station marker draws its watershed; the hover
        # survives the theme toggle since the mouse does not move
        page.locator(hover).first.hover()
        page.wait_for_timeout(300)
    target = page.locator(clip) if clip else page
    target.screenshot(path=shots_dir / f"{name}-dark.png")
    page.keyboard.press("T")
    expect(page.locator("body")).to_have_class(light_re)
    # the light basemap is the dark tiles behind a CSS inversion filter;
    # give the repaint a beat before capturing
    page.wait_for_timeout(200)
    target.screenshot(path=shots_dir / f"{name}-light.png")
    page.keyboard.press("T")
    expect(page.locator("body")).not_to_have_class(light_re)
    print(f"shot {name}")


def settle(page: Page) -> None:
    # blur kills focus rings and unblocks the T hotkey, which the app
    # ignores while an input or select has focus
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.mouse.move(0, 0)
    if page.locator("#map:not(.map--hidden)").count():
        # Leaflet's tile fade is inline-opacity JS, immune to the
        # reduced-motion emulation
        page.wait_for_function(
            """() => {
                const tiles = document.querySelectorAll('#map .leaflet-tile');
                return tiles.length > 0 && [...tiles].every(
                    (t) => t.classList.contains('leaflet-tile-loaded'));
            }"""
        )
        page.wait_for_timeout(300)
    page.evaluate("document.fonts.ready")
    page.wait_for_timeout(100)


def pan_map(page: Page, target_x: float, target_y: float) -> None:
    # drag the map until the calibration marker sits at the target
    # viewport point, in bounded chunks so the grab point stays over the
    # map; the pause before mouse-up kills leaflet's inertia
    marker = page.locator(".map__marker--calibration").first
    for _ in range(8):
        box = marker.bounding_box()
        assert box is not None
        dx = target_x - (box["x"] + box["width"] / 2)
        dy = target_y - (box["y"] + box["height"] / 2)
        if abs(dx) < 20 and abs(dy) < 20:
            return
        step_x = max(-300.0, min(300.0, dx))
        step_y = max(-300.0, min(300.0, dy))
        page.mouse.move(450, 300)
        page.mouse.down()
        page.mouse.move(450 + step_x, 300 + step_y, steps=10)
        page.wait_for_timeout(150)
        page.mouse.up()
        page.wait_for_timeout(300)
    raise RuntimeError("map pan did not converge on the target")


def close_details(page: Page, selector: str) -> None:
    details = page.locator(selector)
    if details.get_attribute("open") is not None:
        details.locator("summary").click()


def brush_zoom(page: Page) -> None:
    box = page.locator("#calibration__streamflow-svg").bounding_box()
    assert box is not None
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + box["width"] * 0.55, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.75, y, steps=10)
    page.mouse.up()
    # the zoom animates the domain over 750 ms (d3, not CSS)
    page.wait_for_timeout(1_000)


def reset_zoom(page: Page) -> None:
    page.locator("#calibration__streamflow-svg").dblclick()
    page.wait_for_timeout(1_000)


def export_files(
    page: Page, selector: str, out_dir: Path, count: int
) -> list[Path]:
    downloads: list[Download] = []

    def collect(download: Download) -> None:
        downloads.append(download)

    page.on("download", collect)
    page.locator(selector).click()
    for _ in range(100):
        if len(downloads) >= count:
            break
        page.wait_for_timeout(100)
    page.remove_listener("download", collect)
    assert len(downloads) == count
    paths = []
    for download in downloads:
        path = out_dir / download.suggested_filename
        download.save_as(path)
        paths.append(path)
    return paths


if __name__ == "__main__":
    main()
