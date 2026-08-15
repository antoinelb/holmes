"""Shared Playwright drivers for the HOLMES UI.

Used by both the e2e tests and scripts/capture_screenshots.py: every
helper takes the Page as its first argument and waits on the app's own
completion signals (loading classes, chart data-signature) rather than
fixed sleeps, so callers can chain steps without racing the WebSocket.
"""

import os
import re
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import httpx
from playwright.sync_api import Page, expect

root_dir = Path(__file__).parents[2]

step_keys = {
    "Stations": "stations",
    "Weather": "weather",
    "Model": "model",
    "Calibration": "calibration",
    "Simulation": "simulation",
    "Projection": "projection",
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

#### server ####


@contextmanager
def run_server() -> Generator[str]:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "holmes.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=root_dir,
        env=os.environ
        | {
            "RELOAD": "0",
            "DEBUG": "0",
            # the warmed data lives in the checkout, not the user data dir
            "HOLMES_DATA_DIR": str((root_dir / "data").resolve()),
        },
    )
    try:
        _wait_ready(url, proc)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


#### step drivers ####


def goto_app(page: Page) -> None:
    page.goto("/")
    expect(page.locator("#sidebar .pipeline__step")).to_have_count(6)
    # the station options arrive over the websocket: placeholder + 8
    expect(
        page.locator("#controls__calibration-station option")
    ).to_have_count(9)


def goto_step(page: Page, title: str) -> None:
    # located by the language-neutral step id, so the walk also works when
    # the UI is in French (the title attribute is translated)
    button = page.locator(f'#sidebar button[data-step="{step_keys[title]}"]')
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


#### private ####


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_ready(url: str, proc: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"server exited with code {proc.returncode} during startup"
            )
        try:
            httpx.get(f"{url}/version", timeout=2)
            return
        except httpx.TransportError:
            time.sleep(0.25)
    raise RuntimeError(f"server at {url} not ready after 30s")
