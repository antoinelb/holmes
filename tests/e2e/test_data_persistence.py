"""E2E tests for localStorage persistence."""

import pytest
from playwright.sync_api import Page, expect

from .pages import CalibrationPage, SettingsPage


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
            calibration_page.page.locator(
                calibration_page.TRANSFORMATION_SELECT
            )
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

        expect(
            calibration_page.page.locator("section#calibration")
        ).to_be_visible()

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


class TestResetAllButton:
    """Tests for the Reset All button functionality."""

    @pytest.fixture
    def calibration_page(self, app_page: Page) -> CalibrationPage:
        """Get calibration page object."""
        return CalibrationPage(app_page)

    @pytest.fixture
    def settings_page(self, app_page: Page) -> SettingsPage:
        """Get settings page object."""
        return SettingsPage(app_page)

    def test_reset_all_clears_page_selection(self, fresh_page: Page) -> None:
        """Reset all button clears page selection and returns to default."""
        fresh_page.click("#nav button[title='Toggle navigation']")
        fresh_page.wait_for_selector("#nav.nav--open")
        fresh_page.click("#nav nav button:has-text('Projection')")
        fresh_page.wait_for_selector("section#projection:not([hidden])")

        stored = fresh_page.evaluate("localStorage.getItem('holmes--page')")
        assert stored == "projection"

        settings = SettingsPage(fresh_page)
        settings.click_reset_all()
        fresh_page.wait_for_selector("header h1", state="visible")

        expect(fresh_page.locator("section#calibration")).to_be_visible()
        expect(fresh_page.locator("section#projection")).to_be_hidden()

        stored_after = fresh_page.evaluate(
            "localStorage.getItem('holmes--page')"
        )
        assert stored_after is None

    def test_reset_all_clears_theme_preference(self, app_page: Page) -> None:
        """Reset all button clears theme preference and returns to dark theme."""
        settings = SettingsPage(app_page)
        settings.click_toggle_theme()

        assert settings.get_current_theme() == "light"
        stored = app_page.evaluate(
            "localStorage.getItem('holmes--settings--theme')"
        )
        assert stored == "light"

        settings.click_reset_all()
        app_page.wait_for_selector("header h1", state="visible")

        settings_after = SettingsPage(app_page)
        assert settings_after.get_current_theme() == "dark"

        stored_after = app_page.evaluate(
            "localStorage.getItem('holmes--settings--theme')"
        )
        assert stored_after is None

    def test_reset_all_clears_calibration_config(
        self, calibration_page: CalibrationPage, settings_page: SettingsPage
    ) -> None:
        """Reset all button clears calibration configuration and restores defaults."""
        calibration_page.wait_for_loading_complete()
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")
        calibration_page.select_objective("kge")
        calibration_page.select_transformation("sqrt")

        stored_objective = settings_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--objective')"
        )
        stored_transformation = settings_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--transformation')"
        )
        assert stored_objective == "kge"
        assert stored_transformation == "sqrt"

        settings_page.click_reset_all()
        settings_page.page.wait_for_selector("header h1", state="visible")

        calibration_after = CalibrationPage(settings_page.page)
        calibration_after.wait_for_loading_complete()

        stored_objective_after = settings_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--objective')"
        )
        stored_transformation_after = settings_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--transformation')"
        )
        assert stored_objective_after != "kge"
        assert stored_transformation_after != "sqrt"

    def test_reset_all_removes_only_holmes_keys(self, app_page: Page) -> None:
        """Reset all button only removes localStorage keys with 'holmes' prefix."""
        app_page.evaluate(
            "localStorage.setItem('other-app-key', 'should-remain')"
        )
        app_page.evaluate(
            "localStorage.setItem('holmes--test', 'should-be-removed')"
        )

        stored_other = app_page.evaluate(
            "localStorage.getItem('other-app-key')"
        )
        stored_holmes = app_page.evaluate(
            "localStorage.getItem('holmes--test')"
        )
        assert stored_other == "should-remain"
        assert stored_holmes == "should-be-removed"

        settings = SettingsPage(app_page)
        settings.click_reset_all()
        app_page.wait_for_selector("header h1", state="visible")

        stored_other_after = app_page.evaluate(
            "localStorage.getItem('other-app-key')"
        )
        stored_holmes_after = app_page.evaluate(
            "localStorage.getItem('holmes--test')"
        )

        assert stored_other_after == "should-remain"
        assert stored_holmes_after is None

        app_page.evaluate("localStorage.removeItem('other-app-key')")


class TestAllowSaveButton:
    """Tests for the Allow Save checkbox functionality."""

    @pytest.fixture
    def calibration_page(self, app_page: Page) -> CalibrationPage:
        """Get calibration page object."""
        return CalibrationPage(app_page)

    @pytest.fixture
    def settings_page(self, app_page: Page) -> SettingsPage:
        """Get settings page object."""
        return SettingsPage(app_page)

    def test_allow_save_checked_by_default(self, fresh_page: Page) -> None:
        """Allow save checkbox is checked by default."""
        settings = SettingsPage(fresh_page)
        assert settings.is_allow_save_checked()

    def test_allow_save_toggle_updates_localstorage(
        self, fresh_page: Page
    ) -> None:
        """Toggling allow save updates localStorage."""
        settings = SettingsPage(fresh_page)

        # Initially checked and no localStorage value (defaults to true)
        assert settings.is_allow_save_checked()
        stored = fresh_page.evaluate(
            "localStorage.getItem('holmes--can-save')"
        )
        assert stored is None

        # Uncheck - should store "false"
        settings.click_allow_save()
        stored = fresh_page.evaluate(
            "localStorage.getItem('holmes--can-save')"
        )
        assert stored == "false"

        # Check again - should store "true"
        settings.click_allow_save()
        stored = fresh_page.evaluate(
            "localStorage.getItem('holmes--can-save')"
        )
        assert stored == "true"

    def test_allow_save_state_persists_after_reload(
        self, fresh_page: Page
    ) -> None:
        """Allow save state persists after page reload."""
        settings = SettingsPage(fresh_page)

        # Uncheck allow save
        settings.click_allow_save()
        assert not settings.is_allow_save_checked()

        # Reload and verify state persists
        fresh_page.reload()
        fresh_page.wait_for_selector("header h1", state="visible")

        settings_after = SettingsPage(fresh_page)
        assert not settings_after.is_allow_save_checked()

    def test_allow_save_disabled_ignores_stored_config(
        self, calibration_page: CalibrationPage, settings_page: SettingsPage
    ) -> None:
        """When allow save is disabled, stored config is ignored on reload."""
        # Set some non-default calibration config
        calibration_page.wait_for_loading_complete()
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_catchment("Au Saumon")
        calibration_page.select_objective("kge")

        # Verify config is stored
        stored_objective = settings_page.page.evaluate(
            "localStorage.getItem('holmes--calibration--objective')"
        )
        assert stored_objective == "kge"

        # Disable allow save
        settings_page.click_allow_save()

        # Reload the page
        settings_page.page.reload()
        settings_page.page.wait_for_selector("header h1", state="visible")

        calibration_after = CalibrationPage(settings_page.page)
        calibration_after.wait_for_loading_complete()

        # UI should show defaults, not the previously stored values
        expect(
            calibration_after.page.locator(calibration_after.OBJECTIVE_SELECT)
        ).to_have_value("rmse")

    def test_allow_save_reenabled_loads_stored_config(
        self, calibration_page: CalibrationPage, settings_page: SettingsPage
    ) -> None:
        """When allow save is re-enabled, stored config is loaded on reload."""
        # Set some non-default calibration config
        calibration_page.wait_for_loading_complete()
        calibration_page.select_hydro_model("gr4j")
        calibration_page.select_objective("kge")

        # Disable allow save
        settings_page.click_allow_save()

        # Re-enable allow save
        settings_page.click_allow_save()

        # Reload the page
        settings_page.page.reload()
        settings_page.page.wait_for_selector("header h1", state="visible")

        calibration_after = CalibrationPage(settings_page.page)
        calibration_after.wait_for_loading_complete()

        # Now stored config should be loaded
        expect(
            calibration_after.page.locator(calibration_after.OBJECTIVE_SELECT)
        ).to_have_value("kge")

    def test_allow_save_disabled_resets_page_to_default(
        self, fresh_page: Page
    ) -> None:
        """When allow save is disabled, page selection resets to default."""
        # Navigate to projection page
        fresh_page.click("#nav button[title='Toggle navigation']")
        fresh_page.wait_for_selector("#nav.nav--open")
        fresh_page.click("#nav nav button:has-text('Projection')")
        fresh_page.wait_for_selector("section#projection:not([hidden])")

        # Verify page is stored
        stored = fresh_page.evaluate("localStorage.getItem('holmes--page')")
        assert stored == "projection"

        # Disable allow save
        settings = SettingsPage(fresh_page)
        settings.click_allow_save()

        # Reload
        fresh_page.reload()
        fresh_page.wait_for_selector("header h1", state="visible")

        # Page should reset to default (calibration)
        expect(fresh_page.locator("section#calibration")).to_be_visible()
        expect(fresh_page.locator("section#projection")).to_be_hidden()
