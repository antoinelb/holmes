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

from pathlib import Path

import pytest
from playwright.sync_api import Download, Page, expect

from tests.e2e.drivers import (
    assert_simulation_metrics,
    digit_re,
    goto_app,
    goto_step,
    run_sce,
    select_station,
    select_weather_method,
    set_algo_param,
    set_calibration_settings,
    set_model_config,
    set_param_slider,
    set_period,
    wait_chart,
)

pikauba_amont = "061022"
pikauba_aval = "061028"
aux_ecorces = "061020"

sce_max_evaluations = 500

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


#### test-only helpers ####


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
