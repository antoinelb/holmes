from collections.abc import Iterator

import pytest
from playwright.sync_api import Page

from tests.e2e import drivers

#### fixtures ####


@pytest.fixture(scope="session")
def base_url(server: str) -> str:
    return server


@pytest.fixture(scope="session")
def server() -> Iterator[str]:
    with drivers.run_server() as url:
        yield url


@pytest.fixture(autouse=True)
def _set_timeouts(page: Page) -> None:
    # data loads and SCE runs are slow; long waits pass explicit timeouts
    page.set_default_timeout(30_000)
    page.set_default_navigation_timeout(30_000)
