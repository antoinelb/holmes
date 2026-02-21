"""E2E test fixtures for Playwright tests."""

import json
import multiprocessing
import os
import socket
import time
from collections.abc import Generator
from contextlib import closing
from pathlib import Path

import pytest
from playwright.sync_api import Page

# Use "spawn" to avoid fork issues with multi-threaded processes (Playwright)
_mp_context = multiprocessing.get_context("spawn")


def find_free_port() -> int:
    """Find an available port for the test server."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def run_server(host: str, port: int) -> None:
    """Run the HOLMES server in a subprocess."""
    import uvicorn

    from holmes.app import create_app

    os.environ["PYTEST_CURRENT_TEST"] = "true"
    uvicorn.run(
        create_app(),
        host=host,
        port=port,
        log_level="warning",
    )


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """Configure browser context with appropriate viewport and settings."""
    return {
        **browser_context_args,
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="session")
def server_url() -> Generator[str, None, None]:
    """Start the HOLMES server for E2E tests."""
    host = "127.0.0.1"
    port = find_free_port()

    server_process = _mp_context.Process(target=run_server, args=(host, port))
    server_process.start()

    url = f"http://{host}:{port}"
    max_wait = 10
    start_time = time.time()

    import httpx

    while time.time() - start_time < max_wait:
        try:
            response = httpx.get(url, timeout=1.0)
            if response.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)

    yield url

    server_process.terminate()
    server_process.join(timeout=5)
    if server_process.is_alive():
        server_process.kill()


@pytest.fixture
def app_page(page: Page, server_url: str) -> Page:
    """Navigate to the app and wait for initial load."""
    page.goto(server_url)
    page.wait_for_selector("header h1", state="visible")
    page.wait_for_selector("main section", state="attached")
    return page


@pytest.fixture
def fresh_page(page: Page, server_url: str) -> Page:
    """Navigate to the app with cleared localStorage."""
    page.goto(server_url)
    page.evaluate("localStorage.clear()")
    page.reload()
    page.wait_for_selector("header h1", state="visible")
    return page


@pytest.fixture
def valid_calibration_json() -> dict:
    """Valid calibration parameters for testing."""
    return {
        "hydroModel": "gr4j",
        "catchment": "Au Saumon",
        "objective": "nse",
        "transformation": "none",
        "algorithm": "manual",
        "algorithmParams": None,
        "start": "2000-01-01",
        "end": "2001-12-31",
        "snowModel": "none",
        "hydroParams": {"x1": 350.0, "x2": 0.5, "x3": 90.0, "x4": 1.7},
    }


@pytest.fixture
def calibration_file(tmp_path: Path, valid_calibration_json: dict) -> Path:
    """Create a temporary calibration JSON file for upload tests."""
    file_path = tmp_path / "calibration.json"
    file_path.write_text(json.dumps(valid_calibration_json))
    return file_path


# --- TP2/TP3 workflow fixtures ---


@pytest.fixture
def leaf_calibration_json() -> dict:
    """Calibration config for Leaf catchment: GR4J, no snow, RMSE."""
    return {
        "hydroModel": "gr4j",
        "catchment": "Leaf",
        "objective": "rmse",
        "transformation": "none",
        "algorithm": "sce",
        "algorithmParams": {
            "seed": 0,
            "n_complexes": 25,
            "max_evaluations": 200,
            "k_stop": 10,
            "p_convergence_threshold": 0.001,
            "geometric_range_threshold": 0.001,
        },
        "start": "1973-01-01",
        "end": "1977-12-31",
        "snowModel": "none",
        "hydroParams": {"x1": 350.0, "x2": 0.5, "x3": 90.0, "x4": 1.7},
    }


@pytest.fixture
def baskatong_calibration_json() -> dict:
    """Calibration config for Baskatong catchment: GR4J, CemaNeige, RMSE."""
    return {
        "hydroModel": "gr4j",
        "catchment": "Baskatong",
        "objective": "rmse",
        "transformation": "none",
        "algorithm": "sce",
        "algorithmParams": {
            "seed": 0,
            "n_complexes": 25,
            "max_evaluations": 200,
            "k_stop": 10,
            "p_convergence_threshold": 0.001,
            "geometric_range_threshold": 0.001,
        },
        "start": "1999-01-01",
        "end": "2003-12-31",
        "snowModel": "cemaneige",
        "hydroParams": {"x1": 400.0, "x2": -0.5, "x3": 100.0, "x4": 1.8},
    }


@pytest.fixture
def au_saumon_snow_calibration_json() -> dict:
    """Calibration config for Au Saumon catchment: GR4J, CemaNeige, RMSE."""
    return {
        "hydroModel": "gr4j",
        "catchment": "Au Saumon",
        "objective": "rmse",
        "transformation": "none",
        "algorithm": "sce",
        "algorithmParams": {
            "seed": 0,
            "n_complexes": 25,
            "max_evaluations": 200,
            "k_stop": 10,
            "p_convergence_threshold": 0.001,
            "geometric_range_threshold": 0.001,
        },
        "start": "1985-01-01",
        "end": "1999-12-31",
        "snowModel": "cemaneige",
        "hydroParams": {"x1": 300.0, "x2": -0.5, "x3": 80.0, "x4": 1.7},
    }


@pytest.fixture
def leaf_calibration_file(tmp_path: Path, leaf_calibration_json: dict) -> Path:
    """Create a Leaf calibration JSON file."""
    file_path = tmp_path / "leaf_gr4j_params.json"
    file_path.write_text(json.dumps(leaf_calibration_json))
    return file_path


@pytest.fixture
def baskatong_calibration_file(
    tmp_path: Path, baskatong_calibration_json: dict
) -> Path:
    """Create a Baskatong calibration JSON file."""
    file_path = tmp_path / "baskatong_gr4j_params.json"
    file_path.write_text(json.dumps(baskatong_calibration_json))
    return file_path


@pytest.fixture
def au_saumon_snow_calibration_file(
    tmp_path: Path, au_saumon_snow_calibration_json: dict
) -> Path:
    """Create an Au Saumon calibration JSON file with CemaNeige."""
    file_path = tmp_path / "au_saumon_gr4j_params.json"
    file_path.write_text(json.dumps(au_saumon_snow_calibration_json))
    return file_path


@pytest.fixture
def leaf_multiple_calibration_files(
    tmp_path: Path, leaf_calibration_json: dict
) -> list[Path]:
    """Create 3 Leaf calibration files with different hydroParams."""
    import copy

    param_sets = [
        {"x1": 350.0, "x2": 0.5, "x3": 90.0, "x4": 1.7},
        {"x1": 400.0, "x2": 0.3, "x3": 100.0, "x4": 1.9},
        {"x1": 250.0, "x2": -0.2, "x3": 60.0, "x4": 1.3},
    ]
    files = []
    for i, params in enumerate(param_sets):
        cal = copy.deepcopy(leaf_calibration_json)
        cal["hydroParams"] = params
        file_path = tmp_path / f"leaf_gr4j_params_{i}.json"
        file_path.write_text(json.dumps(cal))
        files.append(file_path)
    return files
