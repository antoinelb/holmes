"""E2E tests for error handling scenarios."""

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from .pages import SimulationPage


class TestErrorHandling:
    """Tests for error scenarios."""

    @pytest.fixture
    def simulation_page(self, app_page: Page) -> SimulationPage:
        """Get simulation page object and navigate to it."""
        page = SimulationPage(app_page)
        page.navigate_to_section()
        return page

    def test_invalid_calibration_file_shows_notification(
        self, simulation_page: SimulationPage, tmp_path: Path
    ) -> None:
        """Uploading invalid JSON shows error notification."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text(json.dumps({"foo": "bar"}))

        simulation_page.upload_calibration(invalid_file)

        simulation_page.page.wait_for_selector("#notifications .notification")
        texts = simulation_page.page.locator(
            "#notifications .notification span"
        ).all_text_contents()
        assert any("valid" in t.lower() for t in texts)

    def test_malformed_json_is_ignored(
        self, simulation_page: SimulationPage, tmp_path: Path
    ) -> None:
        """Uploading malformed JSON is handled gracefully (no crash)."""
        malformed_file = tmp_path / "malformed.json"
        malformed_file.write_text("{ not valid json")

        simulation_page.upload_calibration(malformed_file)
        simulation_page.page.wait_for_timeout(500)

        # App should not crash - table should remain hidden
        expect(
            simulation_page.page.locator(simulation_page.CALIBRATIONS_TABLE)
        ).to_be_hidden()

    def test_duplicate_calibration_upload_shows_error(
        self, simulation_page: SimulationPage, calibration_file: Path
    ) -> None:
        """Uploading the same calibration twice shows error."""
        simulation_page.upload_calibration(calibration_file)
        simulation_page.wait_for_table()

        # Clear the file input so the change event fires again for the same file
        simulation_page.page.evaluate(
            f"document.querySelector('{simulation_page.UPLOAD_INPUT}').value = ''"
        )
        simulation_page.upload_calibration(calibration_file)

        simulation_page.page.wait_for_selector(
            "#notifications .notification", timeout=5000
        )
        texts = simulation_page.page.locator(
            "#notifications .notification span"
        ).all_text_contents()
        assert any("already" in t.lower() for t in texts)

    def test_notification_can_be_dismissed(
        self, simulation_page: SimulationPage, tmp_path: Path
    ) -> None:
        """Notifications can be dismissed by clicking."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text(json.dumps({"foo": "bar"}))

        simulation_page.upload_calibration(invalid_file)
        simulation_page.page.wait_for_selector("#notifications .notification")

        initial_count = simulation_page.page.locator(
            "#notifications .notification"
        ).count()
        assert initial_count > 0

        simulation_page.page.locator(
            "#notifications .notification"
        ).first.click()
        simulation_page.page.wait_for_timeout(500)

        final_count = simulation_page.page.locator(
            "#notifications .notification"
        ).count()
        assert final_count < initial_count
