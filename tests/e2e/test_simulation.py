"""E2E tests for simulation workflow."""

import copy
import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from .pages import SimulationPage


class TestSimulationWorkflow:
    """Tests for the simulation module."""

    @pytest.fixture
    def simulation_page(self, app_page: Page) -> SimulationPage:
        """Get simulation page object and navigate to it."""
        page = SimulationPage(app_page)
        page.navigate_to_section()
        return page

    def test_upload_calibration_file(
        self, simulation_page: SimulationPage, calibration_file: Path
    ) -> None:
        """Can upload a valid calibration JSON file."""
        simulation_page.upload_calibration(calibration_file)
        simulation_page.wait_for_table()

        expect(
            simulation_page.page.locator(simulation_page.CONFIG_FORM)
        ).to_be_visible()

    def test_upload_multiple_files_for_multimodel(
        self,
        simulation_page: SimulationPage,
        tmp_path: Path,
        valid_calibration_json: dict,
    ) -> None:
        """Can upload multiple files for multimodel simulation."""
        file1 = tmp_path / "cal1.json"
        file1.write_text(json.dumps(valid_calibration_json))

        cal2 = copy.deepcopy(valid_calibration_json)
        cal2["hydroParams"] = {"x1": 400, "x2": 0.3, "x3": 100, "x4": 2.0}
        file2 = tmp_path / "cal2.json"
        file2.write_text(json.dumps(cal2))

        simulation_page.upload_calibration(file1)
        simulation_page.wait_for_table()
        simulation_page.upload_calibration(file2)
        simulation_page.page.wait_for_timeout(200)

        assert simulation_page.get_calibration_count() == 2
        assert simulation_page.is_multimodel_enabled()

    def test_run_simulation(
        self, simulation_page: SimulationPage, calibration_file: Path
    ) -> None:
        """Run simulation and verify results."""
        simulation_page.upload_calibration(calibration_file)
        simulation_page.wait_for_config()
        simulation_page.wait_for_dates_populated()

        simulation_page.run_simulation()
        simulation_page.wait_for_results()

        assert simulation_page.has_metric_charts()

    def test_reset_date_buttons(
        self, simulation_page: SimulationPage, calibration_file: Path
    ) -> None:
        """Reset buttons restore dates to data bounds."""
        simulation_page.upload_calibration(calibration_file)
        simulation_page.wait_for_config()
        simulation_page.wait_for_dates_populated()

        # Change the date to a known value
        changed_value = "2000-06-01"
        simulation_page.page.evaluate(
            f"""
            const input = document.querySelector('#simulation__start');
            input.value = '{changed_value}';
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        """
        )
        simulation_page.page.wait_for_timeout(100)

        # Verify the change took effect
        expect(
            simulation_page.page.locator(simulation_page.START_DATE)
        ).to_have_value(changed_value)

        simulation_page.reset_start_date()

        # Reset should change the value (to data bounds, not the changed value)
        expect(
            simulation_page.page.locator(simulation_page.START_DATE)
        ).not_to_have_value(changed_value)

    def test_remove_calibration(
        self, simulation_page: SimulationPage, calibration_file: Path
    ) -> None:
        """Can remove uploaded calibration."""
        simulation_page.upload_calibration(calibration_file)
        simulation_page.wait_for_table()

        simulation_page.remove_calibration()

        expect(
            simulation_page.page.locator(simulation_page.CALIBRATIONS_TABLE)
        ).to_be_hidden()

    def test_multimodel_requires_multiple_calibrations(
        self, simulation_page: SimulationPage, calibration_file: Path
    ) -> None:
        """Multimodel checkbox requires at least 2 calibrations."""
        simulation_page.upload_calibration(calibration_file)
        simulation_page.wait_for_table()

        assert not simulation_page.is_multimodel_enabled()

    def test_streamflow_chart_has_zoom(
        self, simulation_page: SimulationPage, calibration_file: Path
    ) -> None:
        """Streamflow chart has zoom brush functionality."""
        simulation_page.upload_calibration(calibration_file)
        simulation_page.wait_for_config()
        simulation_page.wait_for_dates_populated()

        simulation_page.run_simulation()
        simulation_page.wait_for_results()

        assert simulation_page.has_zoom_brush()

    def test_reset_end_date_button(
        self, simulation_page: SimulationPage, calibration_file: Path
    ) -> None:
        """Reset end date button restores to data end (not start)."""
        simulation_page.upload_calibration(calibration_file)
        simulation_page.wait_for_config()
        simulation_page.wait_for_dates_populated()

        original_end = simulation_page.get_end_date()

        # Change end date to a different value
        simulation_page.page.evaluate(
            """
            const input = document.querySelector('#simulation__end');
            input.value = '2000-06-01';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        """
        )
        simulation_page.page.wait_for_timeout(100)

        simulation_page.reset_end_date()

        # Should restore to original end date, not start date
        expect(
            simulation_page.page.locator(simulation_page.END_DATE)
        ).to_have_value(original_end)

    def test_switching_catchment_resets_dates(
        self,
        simulation_page: SimulationPage,
        tmp_path: Path,
        valid_calibration_json: dict,
    ) -> None:
        """Switching to different catchment updates config dates to new catchment's range."""
        # Create calibration for Au Saumon catchment
        file1 = tmp_path / "cal1.json"
        file1.write_text(json.dumps(valid_calibration_json))

        # Create calibration for Leaf catchment (different date range)
        cal2 = copy.deepcopy(valid_calibration_json)
        cal2["catchment"] = "Leaf"
        cal2["start"] = "1990-01-01"
        cal2["end"] = "1991-12-31"
        file2 = tmp_path / "cal2.json"
        file2.write_text(json.dumps(cal2))

        # Upload first calibration
        simulation_page.upload_calibration(file1)
        simulation_page.wait_for_config()
        simulation_page.wait_for_dates_populated()

        first_start = simulation_page.get_start_date()
        first_end = simulation_page.get_end_date()

        # Remove first calibration
        simulation_page.remove_calibration()
        simulation_page.page.wait_for_timeout(200)

        # Upload second calibration (different catchment)
        simulation_page.upload_calibration(file2)
        simulation_page.wait_for_config()
        simulation_page.wait_for_dates_populated()

        # Dates should reflect the new catchment's data range
        second_start = simulation_page.get_start_date()
        second_end = simulation_page.get_end_date()

        # Leaf catchment has different observation dates than Au Saumon
        assert first_start != second_start or first_end != second_end
