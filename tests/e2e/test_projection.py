"""E2E tests for projection workflow."""

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

    # Note: Projection module doesn't have a remove calibration button
    # unlike the simulation module. To change calibration, user uploads
    # a new file which replaces the existing one.
