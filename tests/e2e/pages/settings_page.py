"""Page Object for Settings menu."""

from playwright.sync_api import Page

from .base_page import BasePage


class SettingsPage(BasePage):
    """Page object for the Settings menu."""

    # Selectors
    SETTINGS_CONTAINER = "#settings"
    TOGGLE_BUTTON = "#settings button[title='Toggle settings']"
    THEME_BUTTON = "#theme"
    RESET_BUTTON = "#reset"
    VERSION_DISPLAY = "#version"

    def __init__(self, page: Page):
        super().__init__(page)

    def open_settings(self) -> None:
        """Open the settings menu."""
        if not self.is_open():
            self.page.click(self.TOGGLE_BUTTON)
            self.page.wait_for_selector(
                f"{self.SETTINGS_CONTAINER}.settings--open"
            )

    def close_settings(self) -> None:
        """Close the settings menu."""
        if self.is_open():
            self.page.click(self.TOGGLE_BUTTON)
            self.page.wait_for_selector(
                f"{self.SETTINGS_CONTAINER}:not(.settings--open)"
            )

    def is_open(self) -> bool:
        """Check if settings menu is open."""
        settings = self.page.query_selector(self.SETTINGS_CONTAINER)
        if settings is None:
            return False
        classes = settings.get_attribute("class") or ""
        return "settings--open" in classes

    def click_reset_all(self) -> None:
        """Click the Reset All button."""
        self.open_settings()
        self.page.click(self.RESET_BUTTON)

    def click_toggle_theme(self) -> None:
        """Click the Toggle Theme button."""
        self.open_settings()
        self.page.click(self.THEME_BUTTON)

    def get_current_theme(self) -> str:
        """Get the current theme (dark or light)."""
        body_classes = self.page.locator("body").get_attribute("class") or ""
        return "light" if "light" in body_classes else "dark"

    def get_version(self) -> str:
        """Get the displayed version."""
        version_span = self.page.query_selector(
            f"{self.VERSION_DISPLAY} span:last-child"
        )
        if version_span is None:
            return ""
        return version_span.text_content() or ""
