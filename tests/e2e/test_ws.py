from playwright.sync_api import Page

#### tests ####


def test_connection_timeout_is_20_seconds(page: Page, base_url: str) -> None:
    page.goto("/")
    connection_timeout = page.evaluate(
        """async () => {
            const { WS_CONFIG } = await import(
                "/static/scripts/utils/ws.js"
            );
            return WS_CONFIG.connectionTimeout;
        }"""
    )
    assert connection_timeout == 20_000
