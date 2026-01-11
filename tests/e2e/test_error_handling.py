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

    def test_multiple_notifications_display_correctly(
        self, simulation_page: SimulationPage, tmp_path: Path
    ) -> None:
        """Multiple notifications can be displayed and removed without crashing.

        This tests the setDifference browser compatibility fix.
        """
        # Create multiple invalid files to trigger multiple notifications
        for i in range(3):
            invalid_file = tmp_path / f"invalid_{i}.json"
            invalid_file.write_text(json.dumps({"foo": f"bar_{i}"}))
            simulation_page.upload_calibration(invalid_file)
            simulation_page.page.wait_for_timeout(200)

        # Wait for notifications to appear
        simulation_page.page.wait_for_selector("#notifications .notification")

        # App should not crash - should have at least one notification
        notification_count = simulation_page.page.locator(
            "#notifications .notification"
        ).count()
        assert notification_count >= 1

        # Wait for notifications to auto-dismiss
        simulation_page.page.wait_for_timeout(4000)

        # App should still be responsive after notifications are removed
        expect(simulation_page.page.locator("header h1")).to_be_visible()

    def test_app_handles_console_errors_gracefully(
        self, app_page: Page
    ) -> None:
        """App registers global error handlers."""
        # Verify the global error handlers are registered
        has_onerror = app_page.evaluate("typeof window.onerror === 'function'")
        has_unhandled = app_page.evaluate(
            "typeof window.onunhandledrejection === 'function'"
        )
        assert has_onerror, "window.onerror handler should be registered"
        assert has_unhandled, "window.onunhandledrejection handler should be registered"

    def test_app_functional_after_reload(
        self, app_page: Page
    ) -> None:
        """App remains functional after page reload (WebSocket reconnects)."""
        app_page.reload()
        app_page.wait_for_selector("header h1", state="visible")

        # App should be functional after reload
        sections = app_page.locator("main section").count()
        assert sections == 3, "All three sections should be present"
