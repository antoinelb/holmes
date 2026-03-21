"""E2E tests for projection workflow."""

import csv
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from .pages import ProjectionPage


class TestProjectionWorkflow:
    """Tests for the projection module."""

    @pytest.fixture
    def projection_page(self, app_page: Page) -> ProjectionPage:
        """Get projection page object and navigate to it."""
        page = ProjectionPage(app_page)
        page.navigate_to_section()
        return page

    def test_upload_calibration_file(
        self, projection_page: ProjectionPage, calibration_file: Path
    ) -> None:
        """Can upload a valid calibration JSON file."""
        projection_page.wait_for_loading_complete()
        projection_page.upload_calibration(calibration_file)
        projection_page.wait_for_table()

        expect(
            projection_page.page.locator(projection_page.CALIBRATIONS_TABLE)
        ).to_be_visible()

    def test_cascading_dropdowns(
        self, projection_page: ProjectionPage, calibration_file: Path
    ) -> None:
        """Model selection updates horizon and scenario options."""
        projection_page.wait_for_loading_complete()
        # Wait for WebSocket to be connected before uploading
        projection_page.page.wait_for_timeout(500)
        projection_page.upload_calibration(calibration_file)
        projection_page.wait_for_table()
        projection_page.wait_for_config()

        models = projection_page.get_model_options()
        assert len(models) > 0

        projection_page.select_model(models[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.HORIZON_SELECT}').options.length > 0",
            timeout=5000,
        )

        horizons = projection_page.get_horizon_options()
        assert len(horizons) > 0

    def test_run_projection(
        self, projection_page: ProjectionPage, calibration_file: Path
    ) -> None:
        """Run projection and verify results."""
        projection_page.wait_for_loading_complete()
        # Wait for WebSocket to be connected before uploading
        projection_page.page.wait_for_timeout(500)
        projection_page.upload_calibration(calibration_file)
        projection_page.wait_for_table()
        projection_page.wait_for_config()

        models = projection_page.get_model_options()
        projection_page.select_model(models[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.HORIZON_SELECT}').options.length > 0",
            timeout=5000,
        )
        horizons = projection_page.get_horizon_options()
        projection_page.select_horizon(horizons[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.SCENARIO_SELECT}').options.length > 0",
            timeout=5000,
        )
        scenarios = projection_page.get_scenario_options()
        projection_page.select_scenario(scenarios[0])

        projection_page.run_projection()
        projection_page.wait_for_results(timeout=20000)

        assert projection_page.has_projection_chart()

    def test_projection_shows_results_chart(
        self, projection_page: ProjectionPage, calibration_file: Path
    ) -> None:
        """Projection displays results scatter plot."""
        projection_page.wait_for_loading_complete()
        projection_page.page.wait_for_timeout(500)
        projection_page.upload_calibration(calibration_file)
        projection_page.wait_for_table()
        projection_page.wait_for_config()

        models = projection_page.get_model_options()
        projection_page.select_model(models[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.HORIZON_SELECT}').options.length > 0",
            timeout=5000,
        )
        horizons = projection_page.get_horizon_options()
        projection_page.select_horizon(horizons[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.SCENARIO_SELECT}').options.length > 0",
            timeout=5000,
        )
        scenarios = projection_page.get_scenario_options()
        projection_page.select_scenario(scenarios[0])

        projection_page.run_projection()
        projection_page.wait_for_results(timeout=20000)

        assert projection_page.has_results_chart()

    def test_projection_chart_has_zoom(
        self, projection_page: ProjectionPage, calibration_file: Path
    ) -> None:
        """Projection chart has zoom brush functionality."""
        projection_page.wait_for_loading_complete()
        projection_page.page.wait_for_timeout(500)
        projection_page.upload_calibration(calibration_file)
        projection_page.wait_for_table()
        projection_page.wait_for_config()

        models = projection_page.get_model_options()
        projection_page.select_model(models[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.HORIZON_SELECT}').options.length > 0",
            timeout=5000,
        )
        horizons = projection_page.get_horizon_options()
        projection_page.select_horizon(horizons[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.SCENARIO_SELECT}').options.length > 0",
            timeout=5000,
        )
        scenarios = projection_page.get_scenario_options()
        projection_page.select_scenario(scenarios[0])

        projection_page.run_projection()
        projection_page.wait_for_results(timeout=20000)

        assert projection_page.has_zoom_brush()

    def test_export_csv_content(
        self, projection_page: ProjectionPage, calibration_file: Path
    ) -> None:
        """Exported CSVs have correct columns and non-empty data."""
        projection_page.wait_for_loading_complete()
        projection_page.page.wait_for_timeout(500)
        projection_page.upload_calibration(calibration_file)
        projection_page.wait_for_table()
        projection_page.wait_for_config()

        models = projection_page.get_model_options()
        projection_page.select_model(models[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.HORIZON_SELECT}').options.length > 0",
            timeout=5000,
        )
        horizons = projection_page.get_horizon_options()
        projection_page.select_horizon(horizons[0])

        projection_page.page.wait_for_function(
            f"document.querySelector('{projection_page.SCENARIO_SELECT}').options.length > 0",
            timeout=5000,
        )
        scenarios = projection_page.get_scenario_options()
        projection_page.select_scenario(scenarios[0])

        projection_page.run_projection()
        projection_page.wait_for_results(timeout=20000)

        downloads = projection_page.export_data()
        assert len(downloads) == 2

        # Identify each file by name
        data_download = next(
            d for d in downloads if d.suggested_filename.endswith("_data.csv")
        )
        results_download = next(
            d
            for d in downloads
            if d.suggested_filename.endswith("_results.csv")
        )

        # Verify projection data CSV
        data_rows = list(csv.DictReader(Path(data_download.path()).open()))
        assert len(data_rows) > 0
        data_columns = set(data_rows[0].keys())
        assert "date" in data_columns
        assert "streamflow" in data_columns
        assert "member" in data_columns
        assert "model" in data_columns
        assert "horizon" in data_columns
        assert "scenario" in data_columns

        # Verify results CSV
        results_rows = list(
            csv.DictReader(Path(results_download.path()).open())
        )
        assert len(results_rows) > 0
        results_columns = set(results_rows[0].keys())
        assert "member" in results_columns
        assert "winter_min" in results_columns
        assert "spring_max" in results_columns
        assert "summer_min" in results_columns
        assert "autumn_max" in results_columns
        assert "mean" in results_columns

    # Note: Projection module doesn't have a remove calibration button
    # unlike the simulation module. To change calibration, user uploads
    # a new file which replaces the existing one.
