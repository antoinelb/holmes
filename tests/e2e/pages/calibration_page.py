"""Page Object for Calibration module."""

from playwright.sync_api import Page

from .base_page import BasePage


class CalibrationPage(BasePage):
    """Page object for the Calibration section."""

    # Selectors
    SECTION = "#calibration"
    HYDRO_MODEL_SELECT = "#calibration__hydro-model"
    CATCHMENT_SELECT = "#calibration__catchment"
    SNOW_MODEL_SELECT = "#calibration__snow-model"
    OBJECTIVE_SELECT = "#calibration__objective"
    TRANSFORMATION_SELECT = "#calibration__transformation"
    START_DATE = "#calibration__start"
    END_DATE = "#calibration__end"
    ALGORITHM_SELECT = "#calibration__algorithm"

    MANUAL_CONFIG = "#calibration__manual-config"
    AUTOMATIC_CONFIG = "#calibration__automatic-config"

    RUN_MANUAL_BTN = "#calibration__manual-config input[type='submit']"
    START_CALIBRATION_BTN = "#calibration__automatic__start"
    STOP_CALIBRATION_BTN = "#calibration__automatic__stop"

    RESULTS = "#calibration__results"
    STREAMFLOW_CHART = "#calibration__results__streamflow"
    OBJECTIVE_CHART = "#calibration__results__objective"

    def __init__(self, page: Page):
        super().__init__(page)

    def select_hydro_model(self, model: str) -> None:
        """Select a hydrological model."""
        self.page.select_option(self.HYDRO_MODEL_SELECT, model)

    def select_catchment(self, catchment: str) -> None:
        """Select a catchment."""
        self.page.select_option(self.CATCHMENT_SELECT, catchment)

    def select_snow_model(self, model: str | None) -> None:
        """Select a snow model (or 'none')."""
        value = model if model else "none"
        self.page.select_option(self.SNOW_MODEL_SELECT, value)

    def select_objective(self, objective: str) -> None:
        """Select an objective function."""
        self.page.select_option(self.OBJECTIVE_SELECT, objective)

    def select_transformation(self, transformation: str) -> None:
        """Select a transformation."""
        self.page.select_option(self.TRANSFORMATION_SELECT, transformation)

    def set_date_range(self, start: str, end: str) -> None:
        """Set calibration date range."""
        self.page.fill(self.START_DATE, start)
        self.page.fill(self.END_DATE, end)

    def reset_start_date(self) -> None:
        """Click the reset button for start date."""
        self.page.locator("label[for='calibration__start'] button").click()
        self.page.wait_for_timeout(200)

    def reset_end_date(self) -> None:
        """Click the reset button for end date."""
        self.page.locator("label[for='calibration__end'] button").click()
        self.page.wait_for_timeout(200)

    def select_algorithm(self, algorithm: str) -> None:
        """Select calibration algorithm."""
        self.page.select_option(self.ALGORITHM_SELECT, algorithm)

    def get_parameter_sliders(self) -> list[dict]:
        """Get current parameter slider values."""
        sliders = self.page.query_selector_all(f"{self.MANUAL_CONFIG} .slider")
        params = []
        for slider in sliders:
            number_input = slider.query_selector("input[type='number']")
            if number_input:
                params.append(
                    {
                        "id": number_input.get_attribute("id"),
                        "value": float(number_input.input_value()),
                    }
                )
        return params

    def set_parameter(self, param_id: str, value: float) -> None:
        """Set a parameter value via the slider's number input."""
        self.page.fill(f"#{param_id}", str(value))

    def run_manual_calibration(self) -> None:
        """Click the Run button for manual calibration."""
        self.page.click(self.RUN_MANUAL_BTN)

    def start_automatic_calibration(self) -> None:
        """Start automatic calibration."""
        self.page.click(self.START_CALIBRATION_BTN)

    def stop_automatic_calibration(self) -> None:
        """Stop automatic calibration."""
        self.page.click(self.STOP_CALIBRATION_BTN)

    def is_automatic_running(self) -> bool:
        """Check if automatic calibration is running."""
        stop_btn = self.page.query_selector(self.STOP_CALIBRATION_BTN)
        if stop_btn is None:
            return False
        return stop_btn.get_attribute("hidden") is None

    def wait_for_chart_update(self, timeout: int = 5000) -> None:
        """Wait for streamflow chart to have data (observation path)."""
        self.page.wait_for_selector(
            f"{self.STREAMFLOW_CHART} path",
            state="attached",
            timeout=timeout,
        )

    def wait_for_simulation_result(self, timeout: int = 10000) -> None:
        """Wait for simulation result to be rendered (2 paths: observation + simulation)."""
        self.page.wait_for_function(
            f"document.querySelectorAll('{self.STREAMFLOW_CHART} path').length >= 2",
            timeout=timeout,
        )

    def has_simulation_path(self) -> bool:
        """Check if simulation result is displayed on chart."""
        paths = self.page.query_selector_all(f"{self.STREAMFLOW_CHART} path")
        return len(paths) >= 2

    def has_zoom_brush(self) -> bool:
        """Check if zoom brush is rendered on streamflow chart."""
        brush = self.page.query_selector(f"{self.STREAMFLOW_CHART} .brush")
        return brush is not None

    def export_params_enabled(self) -> bool:
        """Check if export params button is enabled."""
        btn = self.page.query_selector(f"{self.RESULTS} button")
        if btn is None:
            return False
        return btn.get_attribute("disabled") is None

    def get_hydro_model_options(self) -> list[str]:
        """Get available hydro model options."""
        options = self.page.query_selector_all(
            f"{self.HYDRO_MODEL_SELECT} option"
        )
        return [opt.text_content() or "" for opt in options]

    def get_catchment_options(self) -> list[str]:
        """Get available catchment options."""
        options = self.page.query_selector_all(
            f"{self.CATCHMENT_SELECT} option"
        )
        return [opt.text_content() or "" for opt in options]
