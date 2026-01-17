"""E2E tests for calibration workflow."""

import pytest
from playwright.sync_api import Page, expect

from .pages import CalibrationPage


class TestCalibrationWorkflow:
    """Tests for the calibration module."""

    @pytest.fixture
    def calibration_page(self, app_page: Page) -> CalibrationPage:
        """Get calibration page object."""
        return CalibrationPage(app_page)

    def test_initial_config_loads(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Config dropdowns are populated from WebSocket."""
        calibration_page.wait_for_loading_complete()

        hydro_options = calibration_page.get_hydro_model_options()
        assert len(hydro_options) > 0

        catchment_options = calibration_page.get_catchment_options()
        assert len(catchment_options) > 0

    def test_select_hydro_model_updates_parameters(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Selecting hydro model updates parameter sliders."""
        calibration_page.wait_for_loading_complete()
        calibration_page.select_hydro_model("gr4j")

        sliders = calibration_page.page.locator(
            f"{calibration_page.MANUAL_CONFIG} .slider"
        )
        expect(sliders).to_have_count(4)

    def test_parameter_slider_syncs_with_number_input(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Slider and number input stay synchronized."""
        calibration_page.wait_for_loading_complete()
        calibration_page.select_hydro_model("gr4j")

        # Get the first slider's range and number inputs
        first_slider = calibration_page.page.locator(
            f"{calibration_page.MANUAL_CONFIG} .slider"
        ).first
        range_input = first_slider.locator("input[type='range']")
        number_input = first_slider.locator("input[type='number']")

        # Use evaluate to set range input value (fill() doesn't work on range inputs)
        range_input.evaluate(
            """
            element => {
                element.value = "400";
                element.dispatchEvent(new Event('input', { bubbles: true }));
            }
            """
        )

        expect(number_input).to_have_value("400")

    def test_manual_calibration_flow(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Complete manual calibration workflow."""
        calibration_page.wait_for_loading_complete()

        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")
        calibration_page.set_date_range("2000-01-01", "2001-12-31")

        calibration_page.run_manual_calibration()
        calibration_page.wait_for_simulation_result()

        assert calibration_page.has_simulation_path()

    def test_automatic_calibration_start_stop(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Automatic calibration can be started and stopped."""
        calibration_page.wait_for_loading_complete()

        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")
        calibration_page.set_date_range("2000-01-01", "2001-12-31")
        calibration_page.select_algorithm("sce")

        calibration_page.start_automatic_calibration()
        # Wait for stop button to appear (indicates running)
        calibration_page.page.wait_for_selector(
            f"{calibration_page.STOP_CALIBRATION_BTN}:not([hidden])",
            timeout=5000,
        )

        assert calibration_page.is_automatic_running()

        calibration_page.stop_automatic_calibration()
        # Wait for start button to reappear (indicates stopped)
        calibration_page.page.wait_for_selector(
            f"{calibration_page.START_CALIBRATION_BTN}:not([hidden])",
            timeout=5000,
        )

        assert not calibration_page.is_automatic_running()

    def test_config_persists_in_localstorage(
        self, calibration_page: CalibrationPage, server_url: str
    ) -> None:
        """Configuration selections persist in localStorage."""
        calibration_page.wait_for_loading_complete()

        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")

        hydro = calibration_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--hydroModel')"
        )
        assert hydro == "gr4j"

        catchment = calibration_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--catchment')"
        )
        assert catchment == "Au Saumon"

        calibration_page.page.reload()
        calibration_page.page.wait_for_selector("header h1")
        calibration_page.wait_for_loading_complete()

        expect(
            calibration_page.page.locator(calibration_page.HYDRO_MODEL_SELECT)
        ).to_have_value("gr4j")
        expect(
            calibration_page.page.locator(calibration_page.CATCHMENT_SELECT)
        ).to_have_value("Au Saumon")

    def test_date_reset_buttons(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Reset buttons restore dates to catchment bounds."""
        calibration_page.wait_for_loading_complete()
        calibration_page.select_catchment("Au Saumon")

        calibration_page.page.wait_for_function(
            f"document.querySelector('{calibration_page.START_DATE}').value !== ''"
        )
        original_start = calibration_page.page.input_value(
            calibration_page.START_DATE
        )

        # Use evaluate to change value and trigger input event
        calibration_page.page.evaluate(
            """
            const input = document.querySelector('#calibration__start');
            input.value = '2000-06-01';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        """
        )
        calibration_page.page.wait_for_timeout(100)

        calibration_page.reset_start_date()

        expect(
            calibration_page.page.locator(calibration_page.START_DATE)
        ).to_have_value(original_start)

    def test_snow_model_selection(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Snow model can be selected and deselected."""
        calibration_page.wait_for_loading_complete()

        calibration_page.select_snow_model("cemaneige")

        snow = calibration_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--snowModel')"
        )
        assert snow == "cemaneige"

        calibration_page.select_snow_model(None)

        snow = calibration_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--snowModel')"
        )
        assert snow == "none"

    def test_streamflow_chart_has_zoom(
        self, calibration_page: CalibrationPage
    ) -> None:
        """Streamflow chart has zoom brush functionality."""
        calibration_page.wait_for_loading_complete()

        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")
        calibration_page.set_date_range("2000-01-01", "2001-12-31")

        calibration_page.run_manual_calibration()
        calibration_page.wait_for_simulation_result()

        assert calibration_page.has_zoom_brush()
