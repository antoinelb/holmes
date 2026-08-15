"""Autouse isolation fixtures for the unit suite.

`tests/integration/conftest.py` imports these, so they guard both suites;
the e2e suite must never see them (it needs real network and data).
"""

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from starlette.websockets import WebSocketState

import holmes.api
import holmes.api_calibration
import holmes.api_projection
import holmes.experiment
import holmes.utils.paths


class FakeWebSocket:
    """Just enough of a starlette WebSocket for the real `send` to work."""

    def __init__(self) -> None:
        self.state = SimpleNamespace()
        self.client_state = WebSocketState.CONNECTED
        self.sent: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent.append(payload)


@pytest.fixture(autouse=True)
def tmp_data_dir(tmp_path, monkeypatch):
    # data_dir is imported by value (`from holmes.utils.paths import data_dir`)
    # in a few modules, so each holds its own reference to patch; the data
    # and download layers import `paths` as a module and need no entry here
    data_dir = tmp_path / "data"
    results_dir = data_dir / "results"
    # the checkout guarantees these exist, and some code (e.g.
    # `_update_experiment_list`) mkdirs children without parents=True
    results_dir.mkdir(parents=True)
    for module in (
        holmes.utils.paths,
        holmes.api,
    ):
        monkeypatch.setattr(module, "data_dir", data_dir)
    monkeypatch.setattr(holmes.utils.paths, "results_dir", results_dir)
    monkeypatch.setattr(holmes.experiment, "results_dir", results_dir)
    return data_dir


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    # safety net under the higher-level mocks: any real httpx request fails
    # fast instead of touching the network
    def blocked(*args, **kwargs):
        raise RuntimeError("network disabled in tests")

    async def blocked_async(*args, **kwargs):
        raise RuntimeError("network disabled in tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
    monkeypatch.setattr(
        httpx.AsyncHTTPTransport, "handle_async_request", blocked_async
    )


@pytest.fixture(autouse=True)
def _reset_api_state(monkeypatch):
    # module-level caches leak between tests, and the asyncio locks remember
    # the first event loop that acquired them, so both get fresh replacements
    monkeypatch.setattr(holmes.api_calibration, "_data_cache", {})
    monkeypatch.setattr(holmes.api_calibration, "_data_lock", asyncio.Lock())
    monkeypatch.setattr(holmes.api_projection, "_projection_cache", {})
    monkeypatch.setattr(
        holmes.api_projection, "_projection_lock", asyncio.Lock()
    )
    monkeypatch.setattr(holmes.api_projection, "_simulation_cache", {})


@pytest.fixture
def fake_ws() -> Any:
    # typed Any so tests can hand it to handlers annotated with the real
    # starlette WebSocket
    return FakeWebSocket()


@pytest.fixture
def no_sleep(monkeypatch):
    async def instant(_duration) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", instant)
