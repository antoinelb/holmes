"""E2E tests for navigation and localStorage persistence."""

from playwright.sync_api import Page, expect


class TestNavigation:
    """Tests for navigation between modules."""

    def test_default_page_is_calibration(self, fresh_page: Page) -> None:
        """Default page should be calibration when no localStorage."""
        expect(fresh_page.locator("section#calibration")).to_be_visible()
        expect(fresh_page.locator("section#simulation")).to_be_hidden()
        expect(fresh_page.locator("section#projection")).to_be_hidden()

    def test_navigate_to_simulation(self, app_page: Page) -> None:
        """Can navigate to simulation via nav menu."""
        app_page.click("#nav button[title='Toggle navigation']")
        app_page.wait_for_selector("#nav.nav--open")
        app_page.click("#nav nav button:has-text('Simulation')")

        expect(app_page.locator("section#simulation")).to_be_visible()
        expect(app_page.locator("section#calibration")).to_be_hidden()

    def test_navigate_to_projection(self, app_page: Page) -> None:
        """Can navigate to projection via nav menu."""
        app_page.click("#nav button[title='Toggle navigation']")
        app_page.wait_for_selector("#nav.nav--open")
        app_page.click("#nav nav button:has-text('Projection')")

        expect(app_page.locator("section#projection")).to_be_visible()

    def test_navigation_persists_after_refresh(self, app_page: Page) -> None:
        """Selected page persists in localStorage after refresh."""
        app_page.click("#nav button[title='Toggle navigation']")
        app_page.wait_for_selector("#nav.nav--open")
        app_page.click("#nav nav button:has-text('Simulation')")

        page_value = app_page.evaluate("localStorage.getItem('holmes--page')")
        assert page_value == "simulation"

        app_page.reload()
        app_page.wait_for_selector("header h1")

        expect(app_page.locator("section#simulation")).to_be_visible()

    def test_nav_closes_on_outside_click(self, app_page: Page) -> None:
        """Nav menu closes when clicking outside."""
        app_page.click("#nav button[title='Toggle navigation']")
        app_page.wait_for_selector("#nav.nav--open")
        app_page.click("main")

        expect(app_page.locator("#nav")).not_to_have_class("nav--open")

    def test_nav_closes_on_escape_key(self, app_page: Page) -> None:
        """Nav menu closes on Escape key."""
        app_page.click("#nav button[title='Toggle navigation']")
        app_page.wait_for_selector("#nav.nav--open")
        app_page.keyboard.press("Escape")

        expect(app_page.locator("#nav")).not_to_have_class("nav--open")
