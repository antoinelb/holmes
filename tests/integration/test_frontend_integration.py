"""
Frontend integration tests using Playwright.

These tests verify the frontend behavior by automating browser interactions.
They test the complete user workflow including page loading, navigation,
form interactions, and data visualization.

Note: These tests require the HOLMES server to be running on port 8000.
Start the server with: `holmes` or `h` before running these tests.
"""

import subprocess
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright

# Fixtures


@pytest.fixture(scope="module")
def test_server():
    """
    Start the HOLMES server for testing.

    This fixture starts the server before any tests run and stops it after
    all tests complete. The server runs on http://127.0.0.1:8000.
    """
    # Start the server
    server_process = subprocess.Popen(
        ["uvicorn", "src.app:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to be ready
    max_retries = 30
    for i in range(max_retries):
        try:
            req = Request("http://127.0.0.1:8000")
            with urlopen(req, timeout=1) as response:
                if response.status == 200:
                    break
        except (URLError, OSError):
            time.sleep(0.5)
    else:
        server_process.kill()
        raise RuntimeError("Server failed to start within timeout")

    yield server_process

    # Cleanup: terminate the server
    server_process.terminate()
    server_process.wait(timeout=5)
    try:
        server_process.kill()
    except ProcessLookupError:
        pass


@pytest_asyncio.fixture
async def browser_page(test_server):
    """
    Launch browser and navigate to app.

    Depends on test_server fixture to ensure the server is running.
    """
    async with async_playwright() as p:
        browser = await p.firefox.launch()
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:8000")
        yield page
        await browser.close()


# Homepage and loading tests


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_homepage_loads(browser_page):
    """Homepage should load successfully."""
    await browser_page.wait_for_selector("h1")
    title = await browser_page.text_content("h1")
    assert "HOLMES" in title


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_precompile_completes(browser_page):
    """Precompilation should complete."""
    # Wait for loading to disappear
    await browser_page.wait_for_selector(
        "main > .loading", state="hidden", timeout=60000
    )

    # Calibration section should be visible
    calibration = await browser_page.query_selector("#calibration")
    is_visible = await calibration.is_visible()
    assert is_visible


# UI interaction tests


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_theme_toggle(browser_page):
    """Theme toggle should work."""
    # Wait for page to load, theme button may be hidden in DOM
    await browser_page.wait_for_selector(
        "#theme", state="attached", timeout=30000
    )

    # Check initial theme
    body = await browser_page.query_selector("body")
    initial_class = await body.get_attribute("class")

    # Click theme toggle using JavaScript (bypasses visibility issues)
    await browser_page.evaluate("document.querySelector('#theme').click()")

    # Wait a moment for theme change to apply
    await browser_page.wait_for_timeout(100)

    # Check theme changed
    final_class = await body.get_attribute("class")
    assert initial_class != final_class


@pytest.mark.playwright
@pytest.mark.asyncio
async def test_navigation_toggle(browser_page):
    """Navigation should toggle between sections."""
    await browser_page.wait_for_selector("#nav")

    # Open nav
    await browser_page.click("#nav > button")

    # Click simulation
    await browser_page.click("nav button:has-text('Simulation')")

    # Simulation section should be visible
    simulation = await browser_page.query_selector("#simulation")
    is_visible = await simulation.is_visible()
    assert is_visible


# Workflow tests


@pytest.mark.playwright
@pytest.mark.asyncio
@pytest.mark.requires_data
async def test_manual_calibration_workflow(browser_page):
    """Test full manual calibration in browser."""
    # Wait for precompile
    await browser_page.wait_for_selector(
        "main > .loading", state="hidden", timeout=60000
    )

    # Select options
    await browser_page.select_option(
        "#calibration__hydrological-model", "GR4J"
    )
    await browser_page.select_option("#calibration__algorithm", "Manual")

    # Adjust a parameter
    slider = await browser_page.query_selector("#calibration__parameter-x1")
    await slider.fill("400")

    # Click run
    await browser_page.click(
        "#calibration__manual-config input[type='submit']"
    )

    # Wait for results
    await browser_page.wait_for_selector(
        ".results__fig .plotly", timeout=30000
    )

    # Export should be visible
    export_btn = await browser_page.query_selector(".results__export")
    is_visible = await export_btn.is_visible()
    assert is_visible
