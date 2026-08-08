import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page

root_dir = Path(__file__).parents[2]

#### fixtures ####


@pytest.fixture(scope="session")
def base_url(server: str) -> str:
    return server


@pytest.fixture(scope="session")
def server() -> Iterator[str]:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "holmes.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=root_dir,
        env=os.environ | {"RELOAD": "0", "DEBUG": "0"},
    )
    try:
        _wait_ready(url, proc)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(autouse=True)
def _set_timeouts(page: Page) -> None:
    # data loads and SCE runs are slow; long waits pass explicit timeouts
    page.set_default_timeout(30_000)
    page.set_default_navigation_timeout(30_000)


#### private ####


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_ready(url: str, proc: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"server exited with code {proc.returncode} during startup"
            )
        try:
            httpx.get(f"{url}/version", timeout=2)
            return
        except httpx.TransportError:
            time.sleep(0.25)
    raise RuntimeError(f"server at {url} not ready after 30s")
