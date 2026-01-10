"""Page Object for Projection module."""

from pathlib import Path

from playwright.sync_api import Page

from .base_page import BasePage


class ProjectionPage(BasePage):
    """Page object for the Projection section."""

    # Selectors
    SECTION = "#projection"
    UPLOAD_INPUT = "#projection__upload"
    CALIBRATIONS_TABLE = "#projection__calibrations-table"
    CONFIG_FORM = "#projection__config"
    MODEL_SELECT = "#projection__model"
    HORIZON_SELECT = "#projection__horizon"
    SCENARIO_SELECT = "#projection__scenario"
    RUN_BTN = "#projection__config input[type='submit']"
    EXPORT_BTN = "#projection__export"

    RESULTS = "#projection__results"
    PROJECTION_CHART = "#projection__results__projection"

    def __init__(self, page: Page):
        super().__init__(page)

    def navigate_to_section(self) -> None:
        """Navigate to the projection section."""
        self.navigate_to("projection")

    def upload_calibration(self, file_path: Path) -> None:
        """Upload a calibration JSON file."""
        self.page.set_input_files(self.UPLOAD_INPUT, file_path)

    def wait_for_table(self, timeout: int = 5000) -> None:
        """Wait for the calibrations table to appear."""
        self.page.wait_for_selector(
            f"{self.CALIBRATIONS_TABLE}:not([hidden])", timeout=timeout
        )

    def wait_for_config(self, timeout: int = 15000) -> None:
        """Wait for config form to be ready (dropdowns populated)."""
        # Wait for WebSocket config response to be processed
        self.page.wait_for_function(
            f"document.querySelector('{self.MODEL_SELECT}').options.length > 0",
            timeout=timeout,
        )

    def select_model(self, model: str) -> None:
        """Select a climate model."""
        self.page.select_option(self.MODEL_SELECT, model)

    def select_horizon(self, horizon: str) -> None:
        """Select a projection horizon."""
        self.page.select_option(self.HORIZON_SELECT, horizon)

    def select_scenario(self, scenario: str) -> None:
        """Select a climate scenario."""
        self.page.select_option(self.SCENARIO_SELECT, scenario)

    def get_model_options(self) -> list[str]:
        """Get available climate model options."""
        options = self.page.query_selector_all(f"{self.MODEL_SELECT} option")
        return [opt.get_attribute("value") or "" for opt in options]

    def get_horizon_options(self) -> list[str]:
        """Get available horizon options."""
        options = self.page.query_selector_all(f"{self.HORIZON_SELECT} option")
        return [opt.get_attribute("value") or "" for opt in options]

    def get_scenario_options(self) -> list[str]:
        """Get available scenario options."""
        options = self.page.query_selector_all(f"{self.SCENARIO_SELECT} option")
        return [opt.get_attribute("value") or "" for opt in options]

    def run_projection(self) -> None:
        """Click the Run button."""
        self.page.click(self.RUN_BTN)

    def wait_for_results(self, timeout: int = 10000) -> None:
        """Wait for projection results (export button appears)."""
        self.page.wait_for_selector(
            f"{self.EXPORT_BTN}:not([hidden])", timeout=timeout
        )

    def has_projection_chart(self) -> bool:
        """Check if projection chart is rendered with paths."""
        paths = self.page.query_selector_all(f"{self.PROJECTION_CHART} path")
        return len(paths) > 0

    def remove_calibration(self) -> None:
        """Remove the uploaded calibration."""
        self.page.locator(f"{self.CALIBRATIONS_TABLE} button").first.click()
