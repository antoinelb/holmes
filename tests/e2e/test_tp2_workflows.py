"""E2E tests for TP2 workflows: calibration and simulation validation.

Covers the step-by-step lab assignment workflow:
- Manual calibration on Baskatong (CemaNeige)
- Automatic calibration with SCE-UA, different objectives, periods, seeds
- Simulation validation on independent periods
- Export functionality for parameters and data
"""

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

from .pages import CalibrationPage, SimulationPage


class TestTP2ManualCalibration:
    """TP2 steps 3-5: Manual calibration workflow."""

    @pytest.fixture
    def calibration_page(self, app_page: Page) -> CalibrationPage:
        page = CalibrationPage(app_page)
        page.wait_for_loading_complete()
        return page

    def test_manual_calibration_baskatong_with_cemaneige(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP2 step 5: GR4J + CemaNeige on Baskatong, manual calibration."""
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Baskatong")
        calibration_page.select_snow_model("cemaneige")
        calibration_page.select_objective("rmse")
        calibration_page.select_transformation("none")
        calibration_page.set_date_range("1999-01-01", "2003-12-31")

        calibration_page.run_manual_calibration()
        calibration_page.wait_for_simulation_result()

        assert calibration_page.has_simulation_path()

    def test_iterative_parameter_adjustment(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP2 step 4b-d: Adjust parameters and re-run to see chart update."""
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Baskatong")
        calibration_page.select_snow_model("cemaneige")
        calibration_page.select_objective("rmse")
        calibration_page.set_date_range("1999-01-01", "2003-12-31")

        # First run with default params
        calibration_page.run_manual_calibration()
        calibration_page.wait_for_simulation_result()
        assert calibration_page.has_simulation_path()

        # Change a parameter and re-run
        sliders = calibration_page.get_parameter_sliders()
        assert len(sliders) > 0
        first_param_id = sliders[0]["id"]
        calibration_page.set_parameter(first_param_id, 500.0)

        calibration_page.run_manual_calibration()
        calibration_page.wait_for_simulation_result()

        # Chart should still display results after re-run
        assert calibration_page.has_simulation_path()

    def test_export_manual_calibration_params(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP2 step 4e: Export params after manual calibration on Baskatong."""
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Baskatong")
        calibration_page.select_snow_model("cemaneige")
        calibration_page.select_objective("rmse")
        calibration_page.select_transformation("none")
        calibration_page.set_date_range("1999-01-01", "2003-12-31")

        calibration_page.run_manual_calibration()
        calibration_page.wait_for_simulation_result()

        download = calibration_page.export_params(algorithm="manual")

        assert download.suggested_filename == "baskatong_gr4j_params.json"

        # Verify JSON content has hydroParams keys
        path = download.path()
        content = json.loads(Path(path).read_text())
        assert "hydroParams" in content
        hydro_params = content["hydroParams"]
        assert set(hydro_params.keys()) == {"x1", "x2", "x3", "x4"}


class TestTP2AutomaticCalibration:
    """TP2 steps 6-11: Automatic calibration with SCE-UA."""

    @pytest.fixture
    def calibration_page(self, app_page: Page) -> CalibrationPage:
        page = CalibrationPage(app_page)
        page.wait_for_loading_complete()
        return page

    def _configure_auto_calibration(
        self,
        cal: CalibrationPage,
        catchment: str,
        snow_model: str | None,
        start: str,
        end: str,
        transformation: str = "none",
        max_evaluations: int = 200,
    ) -> None:
        """Helper to set up automatic calibration config."""
        cal.select_hydro_model("gr4j")
        cal.select_catchment(catchment)
        cal.select_objective("rmse")
        cal.select_transformation(transformation)
        if snow_model is not None:
            cal.select_snow_model(snow_model)
        cal.set_date_range(start, end)
        cal.select_algorithm("sce")
        cal.set_automatic_param("max_evaluations", max_evaluations)

    def test_auto_calibration_baskatong_with_snow(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP2 step 9: Auto calibration on Baskatong with CemaNeige."""
        self._configure_auto_calibration(
            calibration_page,
            catchment="Baskatong",
            snow_model="cemaneige",
            start="1999-01-01",
            end="2003-12-31",
        )

        calibration_page.start_automatic_calibration()
        calibration_page.wait_for_automatic_complete()

        assert calibration_page.has_simulation_path()

    def test_auto_calibration_log_transformation(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP2 step 10: Auto calibration with log transformation."""
        self._configure_auto_calibration(
            calibration_page,
            catchment="Baskatong",
            snow_model="cemaneige",
            start="1999-01-01",
            end="2003-12-31",
            transformation="log",
        )

        calibration_page.start_automatic_calibration()
        calibration_page.wait_for_automatic_complete()

        assert calibration_page.has_simulation_path()

    def test_auto_calibration_different_periods(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP2 step 7: Auto calibration on two different periods."""
        # Period A
        self._configure_auto_calibration(
            calibration_page,
            catchment="Baskatong",
            snow_model="cemaneige",
            start="1999-01-01",
            end="1999-12-31",
        )
        calibration_page.start_automatic_calibration()
        calibration_page.wait_for_automatic_complete()
        assert calibration_page.has_simulation_path()

        # Period B — reconfigure dates and re-run
        calibration_page.set_date_range("2000-01-01", "2000-12-31")
        calibration_page.start_automatic_calibration()
        calibration_page.wait_for_automatic_complete()
        assert calibration_page.has_simulation_path()

    def test_export_auto_calibration_params(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP2 step 7a: Export params after auto calibration."""
        self._configure_auto_calibration(
            calibration_page,
            catchment="Baskatong",
            snow_model="cemaneige",
            start="1999-01-01",
            end="2003-12-31",
        )

        calibration_page.start_automatic_calibration()
        calibration_page.wait_for_automatic_complete()

        download = calibration_page.export_params(algorithm="automatic")

        assert download.suggested_filename == "baskatong_gr4j_params.json"

        path = download.path()
        content = json.loads(Path(path).read_text())
        assert "hydroParams" in content
        assert set(content["hydroParams"].keys()) == {"x1", "x2", "x3", "x4"}

    @pytest.mark.timeout(360)
    def test_equifinality_repeated_runs(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP2 step 11: Equifinality — 3 runs with different seeds produce results."""
        results = []

        for seed in [0, 1, 2]:
            self._configure_auto_calibration(
                calibration_page,
                catchment="Baskatong",
                snow_model="cemaneige",
                start="1999-01-01",
                end="2003-12-31",
            )
            calibration_page.set_automatic_param("seed", seed)

            calibration_page.start_automatic_calibration()
            calibration_page.wait_for_automatic_complete()

            download = calibration_page.export_params(algorithm="automatic")
            path = download.path()
            content = json.loads(Path(path).read_text())
            results.append(content["hydroParams"])

        # All 3 runs should produce valid results
        assert len(results) == 3
        for params in results:
            assert set(params.keys()) == {"x1", "x2", "x3", "x4"}


class TestTP2SimulationValidation:
    """TP2 step 8-9d: Simulation validation on independent periods."""

    @pytest.fixture
    def simulation_page(self, app_page: Page) -> SimulationPage:
        page = SimulationPage(app_page)
        page.navigate_to_section()
        return page

    def test_validate_baskatong_on_independent_period(
        self,
        simulation_page: SimulationPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP2 step 9d: Validate Baskatong on independent period."""
        simulation_page.upload_calibration(baskatong_calibration_file)
        simulation_page.wait_for_config()
        simulation_page.wait_for_dates_populated()

        simulation_page.set_date_range("2008-01-01", "2017-12-31")
        simulation_page.run_simulation()
        simulation_page.wait_for_results()

        assert simulation_page.has_metric_charts()

    def test_multimodel_validation_baskatong(
        self,
        simulation_page: SimulationPage,
        baskatong_multiple_calibration_files: list[Path],
    ) -> None:
        """TP2 step 8 (multi): Upload 3 calibrations, enable multimodel."""
        # Upload all 3 files one by one
        for file_path in baskatong_multiple_calibration_files:
            simulation_page.upload_calibration(file_path)
            simulation_page.page.wait_for_timeout(300)

        simulation_page.wait_for_table()
        assert simulation_page.get_calibration_count() == 3
        assert simulation_page.is_multimodel_enabled()

        simulation_page.toggle_multimodel()
        simulation_page.wait_for_dates_populated()
        simulation_page.run_simulation()
        simulation_page.wait_for_results(timeout=20000)

        assert simulation_page.has_metric_charts()

    def test_simulation_export_results(
        self,
        simulation_page: SimulationPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP2 step 8: Export simulation results after validation."""
        simulation_page.upload_calibration(baskatong_calibration_file)
        simulation_page.wait_for_config()
        simulation_page.wait_for_dates_populated()

        simulation_page.run_simulation()
        simulation_page.wait_for_results()

        download = simulation_page.export_data()
        assert "baskatong" in download.suggested_filename
        assert "simulation" in download.suggested_filename
