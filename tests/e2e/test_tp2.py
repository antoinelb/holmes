"""E2E simulation of every step of tp2.pdf through the real UI.

Each weather method runs the full assignment: manual GR4J calibration
(tp2 steps 3-4), SCE split-sample test (steps 5-6), short-period
recalibration (step 7) and proxy-basin test (step 8). tp2's four
configurations are covered by the weather-method parametrization
(intrant axis) times the {gr4j, bucket} ensemble (model axis). SCE runs
use a reduced max_evaluations so each calibration takes seconds.
Step 9 (reconstructing July 1996 at Pikauba Aval, outside its observed
record) is weather-independent and runs once, as is the calibration
export -> import round trip.
"""

import re
from pathlib import Path

import pytest
from playwright.sync_api import Download, Page, expect

pikauba_amont = "061022"
pikauba_aval = "061028"
aux_ecorces = "061020"

sce_max_evaluations = 500

step_keys = {
    "Stations": "stations",
    "Weather": "weather",
    "Model": "model",
    "Calibration": "calibration",
    "Simulation": "simulation",
}

weather_figures = [
    "weather__precipitation-calibration",
    "weather__precipitation-simulation",
    "weather__temperature-calibration",
    "weather__temperature-simulation",
]

digit_re = re.compile(r"\d")
kge_re = re.compile(r"kge\s*-?[\d.]")
any_re = re.compile(r".")
loading_re = re.compile(r"hydrographs__figure--loading")
selected_re = re.compile(r"--selected")
active_re = re.compile(r"--active")
locked_re = re.compile(r"pipeline__step--locked")

#### tests ####


@pytest.mark.parametrize(
    "weather_method", ["nearest_stations", "era5", "ministry_grid"]
)
def test_tp2_workflow(
    page: Page, base_url: str, tmp_path: Path, weather_method: str
) -> None:
    goto_app(page)
    phase_manual_calibration(page, weather_method, tmp_path)
    phase_split_sample_test(page, tmp_path)
    phase_short_calibration_period(page)
    phase_proxy_basin_test(page)


def test_step9_july_1996_pikauba_aval(page: Page, base_url: str) -> None:
    # tp2 step 9: reconstruct July 1996 at Pikauba Aval, whose record
    # starts in 2002 — the simulation runs on weather alone, so the
    # hydrograph renders but the metrics stay blank
    goto_app(page)
    select_station(page, "calibration", pikauba_amont)
    set_period(page, "calibration", "1980-01-01", "1984-12-31")
    select_station(page, "simulation", pikauba_aval)
    # the warmup years are prepended before the window, so all of
    # 1993-1996 is evaluated and the models spin up on 1992
    set_period(page, "simulation", "1993-01-01", "1996-12-31")
    goto_step(page, "Weather")
    select_weather_method(page, "nearest_stations")
    goto_step(page, "Calibration")
    wait_chart(page, "calibration__streamflow", timeout=120_000)
    # the entry auto-simulate records an attempt, filling `params` and
    # unlocking the simulation step
    expect(page.locator("#calibration__chip-gr4j")).to_have_text(
        digit_re, timeout=120_000
    )
    goto_step(page, "Simulation")
    # the charts only leave their loading state once the result arrives
    wait_chart(page, "simulation__streamflow", timeout=60_000, min_series=1)
    wait_chart(page, "simulation__metrics", timeout=60_000)
    expect(page.locator("#simulation__chip-gr4j")).to_have_text("kge —")


def test_calibration_import_round_trip(
    page: Page, base_url: str, tmp_path: Path
) -> None:
    # export a manually-adjusted fit, move to another station and period
    # (which wipes the bench), then import the file back: the config diff
    # confirm() is accepted and the whole context plus the fit returns
    goto_app(page)
    select_station(page, "calibration", pikauba_amont)
    set_period(page, "calibration", "1980-01-01", "1984-12-31")
    select_station(page, "simulation", pikauba_amont)
    goto_step(page, "Weather")
    select_weather_method(page, "nearest_stations")
    goto_step(page, "Model")
    set_model_config(page, "single", ["gr4j"], "cemaneige")
    goto_step(page, "Calibration")
    wait_chart(page, "calibration__streamflow", timeout=120_000)
    set_calibration_settings(page, "rmse", "none", "manual")
    expect(page.locator("#calibration__chip-gr4j")).to_have_text(
        digit_re, timeout=120_000
    )
    # a slider move makes the exported fit distinguishable from defaults
    set_param_slider(page, "gr4j", 0)
    export_download(page, "#calibration__export", tmp_path, count=2)
    exported = next(tmp_path.glob("calibration_*.json"))

    goto_step(page, "Stations")
    select_station(page, "calibration", aux_ecorces)
    set_period(page, "calibration", "2010-01-01", "2019-12-31")
    goto_step(page, "Calibration")
    wait_chart(page, "calibration__streamflow", timeout=120_000)

    # the config differs from the file's, so Import asks before replacing
    # through the app-styled modal
    with page.expect_file_chooser() as chooser_info:
        page.locator("#calibration__import").click()
    chooser_info.value.set_files(exported)
    dialog = page.locator("#calibration__import-dialog")
    expect(dialog).to_be_visible()
    dialog.get_by_role("button", name="Replace").click()
    expect(dialog).to_be_hidden()
    # the restored context redraws the chart for the exported station, and
    # the re-simulation refills the objective chip
    expect(
        page.locator("#calibration__streamflow figcaption")
    ).to_contain_text(pikauba_amont, timeout=120_000)
    expect(page.locator("#calibration__chip-gr4j")).to_have_text(
        digit_re, timeout=120_000
    )
    goto_step(page, "Stations")
    expect(page.locator("#controls__calibration-station")).to_have_value(
        pikauba_amont
    )
    expect(page.locator("#controls__calibration-start")).to_have_value(
        "1980-01-01"
    )
    expect(page.locator("#controls__calibration-end")).to_have_value(
        "1984-12-31"
    )


#### phases ####


def phase_manual_calibration(
    page: Page, weather_method: str, tmp_path: Path
) -> None:
    # tp2 steps 3-4: GR4J, Pikauba Amont, RMSE without transformation,
    # 1980-01-01 to 1984-12-31, manual calibration, CemaNeige active
    goto_step(page, "Stations")
    select_station(page, "calibration", pikauba_amont)
    set_period(page, "calibration", "1980-01-01", "1984-12-31")
    # the weather step needs both roles configured to unlock
    select_station(page, "simulation", pikauba_amont)
    wait_chart(page, "hydrographs__calibration", timeout=60_000)
    # one streamflow file per role
    export_download(page, "#stations__export", tmp_path, count=2)

    goto_step(page, "Weather")
    select_weather_method(page, weather_method)
    # one weather file per role
    export_download(page, "#weather__export", tmp_path, count=2)

    goto_step(page, "Model")
    set_model_config(page, "single", ["gr4j"], "cemaneige")

    goto_step(page, "Calibration")
    wait_chart(page, "calibration__streamflow", timeout=120_000)
    set_calibration_settings(page, "rmse", "none", "manual")
    expect(page.locator("#calibration__calibrate")).to_be_hidden()
    # wait for the entry auto-simulate so slider moves are unambiguous
    chip = page.locator("#calibration__chip-gr4j")
    expect(chip).to_have_text(digit_re, timeout=120_000)
    for index in range(4):
        set_param_slider(page, "gr4j", index)
    expect(chip).to_have_text(digit_re)
    observed_and_simulated = page.locator(
        "#calibration__streamflow-svg path.series-line"
    )
    assert observed_and_simulated.count() >= 2
    # params json + series csv
    export_download(page, "#calibration__export", tmp_path, count=2)


def phase_split_sample_test(page: Page, tmp_path: Path) -> None:
    # tp2 steps 5-6: SCE on 1980-1989, validation on 1990-1999; the
    # {gr4j, bucket} ensemble covers tp2's model axis in one run
    goto_step(page, "Stations")
    set_period(page, "calibration", "1980-01-01", "1989-12-31")
    set_period(page, "simulation", "1990-01-01", "1999-12-31")

    goto_step(page, "Model")
    set_model_config(page, "ensemble", ["gr4j", "bucket"], "cemaneige")

    goto_step(page, "Calibration")
    wait_chart(page, "calibration__streamflow", timeout=120_000)
    set_calibration_settings(page, "rmse", "none", "sce")
    set_algo_param(page, "max_evaluations", sce_max_evaluations)
    run_sce(page, ["gr4j", "bucket"])

    goto_step(page, "Simulation")
    assert_simulation_metrics(page, ["gr4j", "bucket"])
    # params json + series csv
    export_download(page, "#simulation__export", tmp_path, count=2)


def phase_short_calibration_period(page: Page) -> None:
    # tp2 step 7: recalibrate on 1996 alone, validate on 1990-1999. the
    # default 3 warmup years are kept: they are prepended (1993-1995), so
    # the whole one-year period is still evaluated
    goto_step(page, "Stations")
    set_period(page, "calibration", "1996-01-01", "1996-12-31")

    goto_step(page, "Calibration")
    wait_chart(page, "calibration__streamflow", timeout=120_000)
    set_calibration_settings(page, "rmse", "none", "sce")
    set_algo_param(page, "max_evaluations", sce_max_evaluations)
    run_sce(page, ["gr4j", "bucket"])

    goto_step(page, "Simulation")
    assert_simulation_metrics(page, ["gr4j", "bucket"])


def phase_proxy_basin_test(page: Page) -> None:
    # tp2 step 8: calibrate on Aux Écorces 2010-2019, validate the
    # parameters on Pikauba Aval over the same period
    goto_step(page, "Stations")
    select_station(page, "calibration", aux_ecorces)
    set_period(page, "calibration", "2010-01-01", "2019-12-31")
    select_station(page, "simulation", pikauba_aval)
    set_period(page, "simulation", "2010-01-01", "2019-12-31")

    goto_step(page, "Calibration")
    wait_chart(page, "calibration__streamflow", timeout=120_000)
    set_calibration_settings(page, "rmse", "none", "sce")
    set_algo_param(page, "max_evaluations", sce_max_evaluations)
    run_sce(page, ["gr4j", "bucket"])

    goto_step(page, "Simulation")
    assert_simulation_metrics(page, ["gr4j", "bucket"])


#### step drivers ####


def goto_app(page: Page) -> None:
    page.goto("/")
    expect(page.locator("#sidebar .pipeline__step")).to_have_count(6)
    # the station options arrive over the websocket: placeholder + 8
    expect(
        page.locator("#controls__calibration-station option")
    ).to_have_count(9)


def goto_step(page: Page, title: str) -> None:
    button = page.locator(f'#sidebar button[title="{title}"]')
    # locked buttons are not disabled: a click would silently no-op
    expect(button).not_to_have_class(locked_re)
    button.click()
    expect(
        page.locator(f'#canvas[data-step="{step_keys[title]}"]')
    ).to_be_attached()


def select_station(page: Page, role: str, station_id: str) -> None:
    select = page.locator(f"#controls__{role}-station")
    expect(select.locator(f'option[value="{station_id}"]')).to_be_attached()
    select.select_option(value=station_id)
    expect(select).to_have_value(station_id)


def set_period(page: Page, role: str, start: str, end: str) -> None:
    start_input = page.locator(f"#controls__{role}-start")
    end_input = page.locator(f"#controls__{role}-end")
    # an intermediate start > end state dispatches a null period and the
    # view then wipes both inputs, so the edge keeping the pair ordered
    # is filled first
    current_end = end_input.input_value()
    if current_end and start > current_end:
        end_input.fill(end)
        start_input.fill(start)
    else:
        start_input.fill(start)
        end_input.fill(end)
    expect(start_input).to_have_value(start)
    expect(end_input).to_have_value(end)


def select_weather_method(page: Page, method: str) -> None:
    button = page.locator(f"#controls__method-{method}")
    # re-clicking a selected method would re-trigger the data load
    if "controls__method--selected" not in (
        button.get_attribute("class") or ""
    ):
        button.click()
    expect(button).to_have_class(selected_re)
    for figure_id in weather_figures:
        wait_chart(page, figure_id, timeout=180_000)


def set_model_config(
    page: Page, mode: str, hydro_models: list[str], snow_model: str
) -> None:
    mode_button = page.locator(f"#model__mode-{mode}")
    # both mode buttons dispatch the same toggle: only click when the
    # wanted mode is not already active
    if "model__mode-btn--active" not in (
        mode_button.get_attribute("class") or ""
    ):
        mode_button.click()
        expect(mode_button).to_have_class(active_re)
    for hydro_model in hydro_models:
        toggle_model_option(page, f"hydro-{hydro_model}", wanted=True)
    selected = page.locator(
        "button[id^='model__option-hydro-'].model__option--selected"
    )
    for element_id in selected.evaluate_all("els => els.map((e) => e.id)"):
        hydro_model = element_id.removeprefix("model__option-hydro-")
        if hydro_model not in hydro_models:
            toggle_model_option(page, f"hydro-{hydro_model}", wanted=False)
    toggle_model_option(page, f"snow-{snow_model}", wanted=True)


def set_calibration_settings(
    page: Page, objective: str, transformation: str, algorithm: str
) -> None:
    settings = {
        "objective": objective,
        "transformation": transformation,
        "algorithm": algorithm,
    }
    for name, value in settings.items():
        select = page.locator(f"#calibration__setting-{name}")
        if select.input_value() != value:
            select.select_option(value=value)
        expect(select).to_have_value(value)


def set_algo_param(page: Page, name: str, value: int) -> None:
    open_details(
        page, "details.controls__details:has(#calibration__algo-params)"
    )
    field = page.locator(f"#calibration__algo-{name}")
    field.fill(str(value))
    expect(field).to_have_value(str(value))


def set_param_slider(page: Page, model: str, index: int) -> None:
    open_details(page, f"details.calibration__model[data-model='{model}']")
    field = page.locator(f"#calibration__slider-{model}-{index}")
    expect(field).to_be_visible()
    low = float(field.get_attribute("min") or 0)
    high = float(field.get_attribute("max") or 1)
    current = float(field.input_value())
    svg = page.locator("#calibration__streamflow-svg")
    signature = svg.get_attribute("data-signature") or ""
    set_slider_input(
        page,
        f"calibration__slider-{model}-{index}",
        format_number(pick_target(low, high, current)),
    )
    # the slider change triggers a simulate whose result appends an
    # attempt, which is part of the chart signature
    expect(svg).not_to_have_attribute(
        "data-signature", signature, timeout=120_000
    )


def run_sce(page: Page, models: list[str], timeout: float = 240_000) -> None:
    button = page.locator("#calibration__calibrate")
    expect(button).to_be_visible()
    expect(button).to_have_attribute("data-mode", "calibrate")
    svg = page.locator("#calibration__streamflow-svg")
    before = attempt_counts(svg.get_attribute("data-signature") or "")
    wanted = [
        (before[i] if i < len(before) else 0) + 1 for i in range(len(models))
    ]
    button.click()
    # completion means every model gained an attempt, read from the chart
    # signature; a transient button state would be racy for fast runs
    page.wait_for_function(
        """(wanted) => {
            const svg = document.getElementById(
                'calibration__streamflow-svg');
            const parts = (svg?.dataset.signature || '').split('|');
            const counts = (parts[parts.length - 5] || '')
                .split(',').map(Number);
            return wanted.every((w, i) => (counts[i] || 0) >= w);
        }""",
        arg=wanted,
        timeout=timeout,
    )
    expect(button).to_have_attribute("data-mode", "calibrate", timeout=timeout)
    for model in models:
        expect(page.locator(f"#calibration__chip-{model}")).to_have_text(
            digit_re
        )
    wait_chart(page, "calibration__objective")


def assert_simulation_metrics(
    page: Page, models: list[str], timeout: float = 240_000
) -> None:
    for model in models:
        expect(page.locator(f"#simulation__chip-{model}")).to_have_text(
            kge_re, timeout=timeout
        )
    wait_chart(page, "simulation__metrics", timeout=timeout)
    wait_chart(page, "simulation__streamflow", timeout=timeout, min_series=2)


def export_download(
    page: Page, selector: str, tmp_path: Path, count: int = 1
) -> None:
    button = page.locator(selector)
    expect(button).to_be_enabled()
    # a click may emit several files (one per role), and nested
    # expect_download waiters would all resolve on the first one, so the
    # downloads are collected from the event instead
    downloads: list[Download] = []

    def collect(download: Download) -> None:
        downloads.append(download)

    page.on("download", collect)
    button.click()
    for _ in range(100):
        if len(downloads) >= count:
            break
        page.wait_for_timeout(100)
    page.remove_listener("download", collect)
    assert len(downloads) == count
    for download in downloads:
        path = tmp_path / download.suggested_filename
        download.save_as(path)
        assert path.stat().st_size > 0


#### shared helpers ####


def wait_chart(
    page: Page,
    figure_id: str,
    timeout: float = 30_000,
    min_series: int = 0,
) -> None:
    figure = page.locator(f"#{figure_id}")
    expect(figure).not_to_have_class(loading_re, timeout=timeout)
    svg = page.locator(f"#{figure_id}-svg")
    expect(svg).to_have_attribute("data-signature", any_re, timeout=timeout)
    if min_series:
        assert svg.locator("path.series-line").count() >= min_series


def toggle_model_option(page: Page, suffix: str, wanted: bool) -> None:
    button = page.locator(f"#model__option-{suffix}")
    is_selected = "model__option--selected" in (
        button.get_attribute("class") or ""
    )
    if is_selected != wanted:
        button.click()
    if wanted:
        expect(button).to_have_class(selected_re)
    else:
        expect(button).not_to_have_class(selected_re)


def set_slider_input(page: Page, input_id: str, value: str) -> None:
    field = page.locator(f"#{input_id}")
    field.fill(value)
    # the paired range input clamps, syncs and fires the change that
    # dispatches the update 500 ms after the number input changes
    page.wait_for_timeout(600)


def open_details(page: Page, selector: str) -> None:
    details = page.locator(selector)
    if details.get_attribute("open") is None:
        details.locator("summary").click()


def pick_target(low: float, high: float, current: float) -> float:
    # any in-bounds value different from the current one works: the goal
    # is only to trigger a simulate with changed parameters
    span = high - low
    midpoint = low + span / 2
    if abs(midpoint - current) > span / 100:
        return round(midpoint, 2)
    return round(low + span / 4, 2)


def format_number(value: float) -> str:
    return f"{value:g}"


def attempt_counts(signature: str) -> list[int]:
    # chartSignature is key|attempts|simulations|objective|warmup|size,
    # and only the leading series key may itself contain pipes, so the
    # attempt counts are the fifth field from the end
    field = signature.split("|")[-5]
    return [int(count) for count in field.split(",") if count]
