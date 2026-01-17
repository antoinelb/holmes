"""Page Object for Simulation module."""

from pathlib import Path

from playwright.sync_api import Page

from .base_page import BasePage


class SimulationPage(BasePage):
    """Page object for the Simulation section."""

    # Selectors
    SECTION = "#simulation"
    UPLOAD_INPUT = "#simulation__upload"
    CALIBRATIONS_TABLE = "#simulation__calibrations-table"
    CONFIG_FORM = "#simulation__config"
    START_DATE = "#simulation__start"
    END_DATE = "#simulation__end"
    MULTIMODEL_CHECKBOX = "#simulation__multimodel"
    RUN_BTN = "#simulation__config input[type='submit']"
    EXPORT_BTN = "#simulation__export"

    RESULTS = "#simulation__results"
    NSE_NONE_CHART = "#simulation__results__nse-none"
    STREAMFLOW_CHART = "#simulation__results__streamflow"

    def __init__(self, page: Page):
        super().__init__(page)

    def navigate_to_section(self) -> None:
        """Navigate to the simulation section."""
        self.navigate_to("simulation")

    def upload_calibration(self, file_path: Path) -> None:
        """Upload a calibration JSON file."""
        self.page.set_input_files(self.UPLOAD_INPUT, file_path)

    def upload_multiple_calibrations(self, file_paths: list[Path]) -> None:
        """Upload multiple calibration JSON files."""
        self.page.set_input_files(self.UPLOAD_INPUT, file_paths)

    def wait_for_table(self, timeout: int = 5000) -> None:
        """Wait for the calibrations table to appear."""
        self.page.wait_for_selector(
            f"{self.CALIBRATIONS_TABLE}:not([hidden])", timeout=timeout
        )

    def wait_for_config(self, timeout: int = 5000) -> None:
        """Wait for the config form to appear."""
        self.page.wait_for_selector(
            f"{self.CONFIG_FORM}:not([hidden])", timeout=timeout
        )

    def get_calibration_count(self) -> int:
        """Get number of uploaded calibrations."""
        rows = self.page.query_selector_all(f"{self.CALIBRATIONS_TABLE} > div")
        return max(0, len(rows) - 1)

    def remove_calibration(self, index: int = 0) -> None:
        """Remove a calibration from the table."""
        self.page.locator(f"{self.CALIBRATIONS_TABLE} button").nth(
            index
        ).click()

    def set_date_range(self, start: str, end: str) -> None:
        """Set simulation date range."""
        self.page.fill(self.START_DATE, start)
        self.page.fill(self.END_DATE, end)

    def reset_start_date(self) -> None:
        """Click the reset button for start date."""
        self.page.locator("label[for='simulation__start'] button").click()
        self.page.wait_for_timeout(200)

    def reset_end_date(self) -> None:
        """Click the reset button for end date."""
        self.page.locator("label[for='simulation__end'] button").click()
        self.page.wait_for_timeout(200)

    def is_multimodel_enabled(self) -> bool:
        """Check if multimodel checkbox is enabled."""
        checkbox = self.page.query_selector(self.MULTIMODEL_CHECKBOX)
        if checkbox is None:
            return False
        return checkbox.get_attribute("disabled") is None

    def toggle_multimodel(self) -> None:
        """Toggle the multimodel checkbox."""
        self.page.click("label[for='simulation__multimodel']")

    def run_simulation(self) -> None:
        """Click the Run button."""
        self.page.click(self.RUN_BTN)

    def wait_for_results(self, timeout: int = 10000) -> None:
        """Wait for simulation results (export button appears)."""
        self.page.wait_for_selector(
            f"{self.EXPORT_BTN}:not([hidden])", timeout=timeout
        )

    def has_metric_charts(self) -> bool:
        """Check if metric charts are rendered."""
        charts = self.page.query_selector_all(f"{self.RESULTS} svg.plot")
        return len(charts) >= 6

    def has_zoom_brush(self) -> bool:
        """Check if zoom brush is rendered on streamflow chart."""
        brush = self.page.query_selector(f"{self.STREAMFLOW_CHART} .brush")
        return brush is not None

    def get_start_date(self) -> str:
        """Get current start date value."""
        return self.page.input_value(self.START_DATE)

    def get_end_date(self) -> str:
        """Get current end date value."""
        return self.page.input_value(self.END_DATE)

    def wait_for_dates_populated(self, timeout: int = 5000) -> None:
        """Wait for dates to be populated from calibration data."""
        self.page.wait_for_function(
            f"document.querySelector('{self.START_DATE}').value !== ''",
            timeout=timeout,
        )
