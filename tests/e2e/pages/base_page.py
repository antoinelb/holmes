"""Base Page Object for common interactions."""

from playwright.sync_api import Page, expect


class BasePage:
    """Base class for all page objects."""

    def __init__(self, page: Page):
        self.page = page

    def navigate_to(self, section: str) -> None:
        """Navigate to a section via the nav menu."""
        self.page.click("#nav button[title='Toggle navigation']")
        self.page.wait_for_selector("#nav.nav--open")
        self.page.click(f"#nav nav button:has-text('{section.title()}')")
        self.page.wait_for_selector(f"section#{section}:not([hidden])")

    def wait_for_loading_complete(self, timeout: int = 5000) -> None:
        """Wait for loading to complete by checking WebSocket connection."""
        self.page.wait_for_load_state("networkidle", timeout=timeout)

    def get_notifications(self) -> list[str]:
        """Get all notification texts."""
        return [
            el.text_content() or ""
            for el in self.page.query_selector_all("#notifications li")
        ]

    def dismiss_notifications(self) -> None:
        """Dismiss all notifications."""
        for close_btn in self.page.query_selector_all("#notifications button"):
            close_btn.click()

    def get_current_page(self) -> str:
        """Get the currently visible page/section."""
        for section in self.page.query_selector_all("section"):
            if not section.get_attribute("hidden"):
                return section.get_attribute("id") or ""
        return ""
