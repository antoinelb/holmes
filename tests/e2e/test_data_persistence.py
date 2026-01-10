"""E2E tests for localStorage persistence."""

import pytest
from playwright.sync_api import Page, expect

from .pages import CalibrationPage


class TestDataPersistence:
    """Tests for localStorage data persistence."""

    @pytest.fixture
    def calibration_page(self, app_page: Page) -> CalibrationPage:
        """Get calibration page object."""
        return CalibrationPage(app_page)

    def test_page_selection_persists(self, fresh_page: Page) -> None:
        """Page selection persists after reload."""
        fresh_page.click("#nav button[title='Toggle navigation']")
        fresh_page.wait_for_selector("#nav.nav--open")
        fresh_page.click("#nav nav button:has-text('Projection')")

        stored = fresh_page.evaluate("localStorage.getItem('holmes--page')")
        assert stored == "projection"

        fresh_page.reload()
        fresh_page.wait_for_selector("header h1")

        expect(fresh_page.locator("section#projection")).to_be_visible()

    def test_calibration_config_persists(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Calibration configuration persists after reload."""
        calibration_page.wait_for_loading_complete()

        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")
        calibration_page.select_objective("nse")
        calibration_page.select_transformation("sqrt")
        calibration_page.select_algorithm("sce")

        calibration_page.page.reload()
        calibration_page.page.wait_for_selector("header h1")
        calibration_page.wait_for_loading_complete()

        expect(
            calibration_page.page.locator(calibration_page.HYDRO_MODEL_SELECT)
        ).to_have_value("gr4j")
        expect(
            calibration_page.page.locator(calibration_page.CATCHMENT_SELECT)
        ).to_have_value("Au Saumon")
        expect(
            calibration_page.page.locator(calibration_page.OBJECTIVE_SELECT)
        ).to_have_value("nse")
        expect(
            calibration_page.page.locator(calibration_page.TRANSFORMATION_SELECT)
        ).to_have_value("sqrt")
        expect(
            calibration_page.page.locator(calibration_page.ALGORITHM_SELECT)
        ).to_have_value("sce")

    def test_clear_localstorage_resets_to_defaults(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Clearing localStorage resets app to default state."""
        calibration_page.wait_for_loading_complete()
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")

        calibration_page.page.evaluate("localStorage.clear()")
        calibration_page.page.reload()
        calibration_page.page.wait_for_selector("header h1")
        calibration_page.wait_for_loading_complete()

        expect(calibration_page.page.locator("section#calibration")).to_be_visible()

    def test_date_range_persists(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Date range selection persists after reload."""
        calibration_page.wait_for_loading_complete()
        calibration_page.select_catchment("Au Saumon")

        calibration_page.page.wait_for_function(
            f"document.querySelector('{calibration_page.START_DATE}').value !== ''"
        )

        calibration_page.set_date_range("2000-06-01", "2001-06-01")

        calibration_page.page.reload()
        calibration_page.page.wait_for_selector("header h1")
        calibration_page.wait_for_loading_complete()

        expect(
            calibration_page.page.locator(calibration_page.START_DATE)
        ).to_have_value("2000-06-01")
        expect(
            calibration_page.page.locator(calibration_page.END_DATE)
        ).to_have_value("2001-06-01")
