"""E2E tests for TP3 workflows: climate projections.

Covers the step-by-step lab assignment workflow:
- Calibrating models for projection (Baskatong, Au Saumon)
- Importing calibrations into projection module
- Configuring climate model, horizon, and scenario
- Running projections and verifying charts, indicators, ensemble members
- Exporting projection data
"""

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page

from .pages import CalibrationPage, ProjectionPage


# --- Helpers ---


def _run_projection_workflow(
    projection_page: ProjectionPage,
    calibration_file: Path,
    model: str,
    horizon: str,
    scenario: str,
    timeout: int = 30000,
) -> None:
    """Upload calibration, configure dropdowns, and run a projection."""
    projection_page.wait_for_loading_complete()
    projection_page.page.wait_for_timeout(500)
    projection_page.upload_calibration(calibration_file)
    projection_page.wait_for_table()
    projection_page.wait_for_config()

    projection_page.select_model(model)
    projection_page.page.wait_for_function(
        f"document.querySelector('{projection_page.HORIZON_SELECT}').options.length > 0",
        timeout=5000,
    )

    projection_page.select_horizon(horizon)
    projection_page.page.wait_for_function(
        f"document.querySelector('{projection_page.SCENARIO_SELECT}').options.length > 0",
        timeout=5000,
    )

    projection_page.select_scenario(scenario)
    projection_page.run_projection()
    projection_page.wait_for_results(timeout=timeout)


class TestTP3CalibrationForProjection:
    """TP3 steps 2-4: Calibrate models to use in projections."""

    @pytest.fixture
    def calibration_page(self, app_page: Page) -> CalibrationPage:
        page = CalibrationPage(app_page)
        page.wait_for_loading_complete()
        return page

    def test_calibrate_baskatong_for_projection(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP3 step 2-4: Auto-calibrate Baskatong with CemaNeige for projection."""
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Baskatong")
        calibration_page.select_snow_model("cemaneige")
        calibration_page.select_objective("rmse")
        calibration_page.select_transformation("none")
        calibration_page.set_date_range("1985-01-01", "1999-12-31")
        calibration_page.select_algorithm("sce")
        calibration_page.set_automatic_param("max_evaluations", 200)

        calibration_page.start_automatic_calibration()
        calibration_page.wait_for_automatic_complete()

        download = calibration_page.export_params(algorithm="automatic")
        assert download.suggested_filename == "baskatong_gr4j_params.json"

        path = download.path()
        content = json.loads(Path(path).read_text())
        assert "hydroParams" in content
        assert content["catchment"] == "Baskatong"
        assert content["snowModel"] == "cemaneige"

    def test_calibrate_au_saumon_for_projection(
        self, calibration_page: CalibrationPage
    ) -> None:
        """TP3 step 7+2-4: Auto-calibrate Au Saumon with CemaNeige for projection."""
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")
        calibration_page.select_snow_model("cemaneige")
        calibration_page.select_objective("rmse")
        calibration_page.select_transformation("none")
        calibration_page.set_date_range("1985-01-01", "1999-12-31")
        calibration_page.select_algorithm("sce")
        calibration_page.set_automatic_param("max_evaluations", 200)

        calibration_page.start_automatic_calibration()
        calibration_page.wait_for_automatic_complete()

        download = calibration_page.export_params(algorithm="automatic")
        assert download.suggested_filename == "au_saumon_gr4j_params.json"

        path = download.path()
        content = json.loads(Path(path).read_text())
        assert "hydroParams" in content
        assert content["catchment"] == "Au Saumon"


class TestTP3ProjectionBaskatong:
    """TP3 steps 5-6: Projection workflows for Baskatong."""

    @pytest.fixture
    def projection_page(self, app_page: Page) -> ProjectionPage:
        page = ProjectionPage(app_page)
        page.navigate_to_section()
        return page

    def test_import_and_configure_projection(
        self,
        projection_page: ProjectionPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP3 step 5: Upload calibration and verify cascading dropdowns."""
        projection_page.wait_for_loading_complete()
        projection_page.page.wait_for_timeout(500)
        projection_page.upload_calibration(baskatong_calibration_file)
        projection_page.wait_for_table()
        projection_page.wait_for_config()

        # Model dropdown should have options
        models = projection_page.get_model_options()
        assert len(models) > 0

        # Select first model → horizons should populate
        projection_page.select_model(models[0])
        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.HORIZON_SELECT}').options.length > 0",
            timeout=5000,
        )
        horizons = projection_page.get_horizon_options()
        assert len(horizons) > 0

        # Select first horizon → scenarios should populate
        projection_page.select_horizon(horizons[0])
        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.SCENARIO_SELECT}').options.length > 0",
            timeout=5000,
        )
        scenarios = projection_page.get_scenario_options()
        assert len(scenarios) > 0

    def test_projection_ref(
        self,
        projection_page: ProjectionPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP3 step 6 case 1: Baskatong projection with REF horizon/scenario."""
        _run_projection_workflow(
            projection_page,
            baskatong_calibration_file,
            model="CSI",
            horizon="REF",
            scenario="REF",
        )

        assert projection_page.has_projection_chart()
        assert projection_page.has_results_chart()

    def test_projection_rcp45_h50(
        self,
        projection_page: ProjectionPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP3 step 6 case 2: Baskatong projection with H50 horizon, RCP4.5."""
        _run_projection_workflow(
            projection_page,
            baskatong_calibration_file,
            model="CSI",
            horizon="H50",
            scenario="RCP4.5",
        )

        assert projection_page.has_projection_chart()
        assert projection_page.has_results_chart()

    def test_projection_rcp85_h50(
        self,
        projection_page: ProjectionPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP3 step 6 case 3: Baskatong projection with H50 horizon, RCP8.5."""
        _run_projection_workflow(
            projection_page,
            baskatong_calibration_file,
            model="CSI",
            horizon="H50",
            scenario="RCP8.5",
        )

        assert projection_page.has_projection_chart()
        assert projection_page.has_results_chart()

    def test_projection_five_indicators(
        self,
        projection_page: ProjectionPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP3 step 6 indicators: Results chart shows 5 indicator labels."""
        _run_projection_workflow(
            projection_page,
            baskatong_calibration_file,
            model="CSI",
            horizon="REF",
            scenario="REF",
        )

        indicator_count = projection_page.get_results_indicator_count()
        assert indicator_count == 5

    def test_projection_ensemble_members(
        self,
        projection_page: ProjectionPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP3 step 5: Projection chart shows >= 10 paths (members + median)."""
        _run_projection_workflow(
            projection_page,
            baskatong_calibration_file,
            model="CSI",
            horizon="REF",
            scenario="REF",
        )

        path_count = projection_page.get_projection_path_count()
        # Each ensemble member produces a path, plus median = 10+ paths
        assert path_count >= 10

    def test_projection_export(
        self,
        projection_page: ProjectionPage,
        baskatong_calibration_file: Path,
    ) -> None:
        """TP3 step 6 save: Export triggers 2 downloads (data + results CSVs)."""
        _run_projection_workflow(
            projection_page,
            baskatong_calibration_file,
            model="CSI",
            horizon="REF",
            scenario="REF",
        )

        downloads = projection_page.export_data()

        assert len(downloads) == 2
        filenames = {d.suggested_filename for d in downloads}
        assert "baskatong_projection_data.csv" in filenames
        assert "baskatong_projection_results.csv" in filenames


class TestTP3ProjectionAuSaumon:
    """TP3 step 7+6: Projection workflows for Au Saumon."""

    @pytest.fixture
    def projection_page(self, app_page: Page) -> ProjectionPage:
        page = ProjectionPage(app_page)
        page.navigate_to_section()
        return page

    def test_au_saumon_projection_ref(
        self,
        projection_page: ProjectionPage,
        au_saumon_snow_calibration_file: Path,
    ) -> None:
        """TP3 step 7+6 case 1: Au Saumon projection REF horizon/scenario."""
        _run_projection_workflow(
            projection_page,
            au_saumon_snow_calibration_file,
            model="CSI",
            horizon="REF",
            scenario="REF",
        )

        assert projection_page.has_projection_chart()
        assert projection_page.has_results_chart()

    def test_au_saumon_projection_rcp45_h50(
        self,
        projection_page: ProjectionPage,
        au_saumon_snow_calibration_file: Path,
    ) -> None:
        """TP3 step 7+6 case 2: Au Saumon projection H50/RCP4.5."""
        _run_projection_workflow(
            projection_page,
            au_saumon_snow_calibration_file,
            model="CSI",
            horizon="H50",
            scenario="RCP4.5",
        )

        assert projection_page.has_projection_chart()
        assert projection_page.has_results_chart()

    def test_au_saumon_projection_rcp85_h50(
        self,
        projection_page: ProjectionPage,
        au_saumon_snow_calibration_file: Path,
    ) -> None:
        """TP3 step 7+6 case 3: Au Saumon projection H50/RCP8.5."""
        _run_projection_workflow(
            projection_page,
            au_saumon_snow_calibration_file,
            model="CSI",
            horizon="H50",
            scenario="RCP8.5",
        )

        assert projection_page.has_projection_chart()
        assert projection_page.has_results_chart()
