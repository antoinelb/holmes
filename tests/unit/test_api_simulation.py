import asyncio
import warnings
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import holmes_rs
import numpy as np
import pytest

import holmes.api_simulation as simulation
import holmes.data.joined

gr4j_defaults = list(holmes_rs.hydro.gr4j.init()[0])
bucket_defaults = list(holmes_rs.hydro.bucket.init()[0])

valid_msg = {
    "type": "simulation_data",
    "station": "061004",
    "method": "ministry_grid",
    "start": "2016-01-01",
    "end": "2016-12-31",
    "hydroModels": ["gr4j", "bucket"],
    "snowModel": "none",
    "requestId": 5,
    "warmupYears": 1,
    "n_stations": 3,
    "hydroParams": {"gr4j": gr4j_defaults, "bucket": bucket_defaults},
}


@pytest.fixture
def joined_data(monkeypatch, joined_df):
    monkeypatch.setattr(
        holmes.data.joined,
        "read_joined_data",
        MagicMock(return_value=joined_df),
    )


class TestHandleSimulationMessage:
    async def test_dispatches_data(self, monkeypatch, fake_ws):
        mock = AsyncMock()
        monkeypatch.setattr(simulation, "_handle_data", mock)
        await simulation.handle_simulation_message(
            fake_ws, {"type": "simulation_data"}
        )
        mock.assert_awaited_once()

    async def test_other_types_are_ignored(self, fake_ws):
        await simulation.handle_simulation_message(fake_ws, {"type": "bogus"})
        assert fake_ws.sent == []


class TestHandleData:
    @pytest.mark.parametrize(
        ["overrides", "match"],
        [
            ({"station": "999"}, "Unknown station"),
            ({"method": "bogus"}, "Unknown weather method"),
            ({"start": "x"}, "Invalid simulation date range"),
            ({"n_stations": 0}, "Invalid number of nearest stations"),
            ({"hydroModels": "gr4j"}, "Unknown hydro model"),
            ({"hydroModels": []}, "Unknown hydro model"),
            ({"hydroModels": ["bogus"]}, "Unknown hydro model"),
            ({"snowModel": "bogus"}, "Unknown snow model"),
            ({"warmupYears": -1}, "Invalid numeric simulation field"),
            ({"requestId": "x"}, "Invalid numeric simulation field"),
            ({"hydroParams": []}, "Invalid hydro parameters"),
            (
                {"hydroParams": {"gr4j": gr4j_defaults}},
                "Invalid hydro parameters for bucket",
            ),
            (
                {"snowModel": "cemaneige", "snowParams": ["x"]},
                "Invalid snow parameters",
            ),
        ],
    )
    async def test_validation_errors(self, fake_ws, overrides, match):
        await simulation._handle_data(fake_ws, {**valid_msg, **overrides})
        assert fake_ws.sent[0]["type"] == "error"
        assert match in fake_ws.sent[0]["data"]

    async def test_supersedes_pending_run(self, monkeypatch, fake_ws):
        monkeypatch.setattr(simulation, "_load_simulation", AsyncMock())
        pending = asyncio.create_task(asyncio.Event().wait())
        await asyncio.sleep(0)
        fake_ws.state.simulation_task = pending
        await simulation._handle_data(fake_ws, valid_msg)
        assert pending.cancelled() or pending.cancelling()
        await fake_ws.state.simulation_task


class TestLoadSimulation:
    @staticmethod
    async def run(fake_ws, **overrides):
        args: dict[str, Any] = {
            "station": "061004",
            "start": "2016-01-01",
            "end": "2016-12-31",
            "method": "ministry_grid",
            "n_stations": 3,
            "hydro_models": ["gr4j", "bucket"],
            "snow_model": None,
            "hydro_params": {
                "gr4j": gr4j_defaults,
                "bucket": bucket_defaults,
            },
            "snow_params": None,
            "warmup_years": 1,
            "request_id": 5,
        }
        args.update(overrides)
        await simulation._load_simulation(fake_ws, **args)

    async def test_simulates_every_model_and_median(
        self, fake_ws, joined_data
    ):
        await self.run(fake_ws)
        reply = fake_ws.sent[0]
        assert reply["type"] == "simulation_result"
        assert reply["data"]["requestId"] == 5
        assert set(reply["data"]["results"]) == {"gr4j", "bucket"}
        assert len(reply["data"]["median"]["simulation"]) == 366 + 365
        assert reply["data"]["median"]["metrics"]["kge"] is not None

    async def test_with_snow(self, fake_ws, joined_data):
        await self.run(
            fake_ws,
            hydro_models=["gr4j"],
            hydro_params={"gr4j": gr4j_defaults},
            snow_model="cemaneige",
            snow_params=[0.25, 3.74, 300.0],
        )
        assert fake_ws.sent[0]["type"] == "simulation_result"

    async def test_empty_window_sends_error(self, fake_ws, joined_data):
        await self.run(fake_ws, start="1990-01-01", end="1990-12-31")
        reply = fake_ws.sent[0]
        assert reply["type"] == "simulation_error"
        assert "No data for station" in reply["data"]["message"]

    async def test_failure_sends_error(self, fake_ws, joined_data):
        await self.run(fake_ws, hydro_params={"gr4j": [1.0], "bucket": [1.0]})
        reply = fake_ws.sent[0]
        assert reply["type"] == "simulation_error"
        assert "Failed to run simulation" in reply["data"]["message"]


class TestEvaluateMedian:
    def test_pointwise_median_skips_non_finite(self):
        observations = np.full(4, 2.0)
        simulations = [
            np.array([1.0, 1.0, np.nan, np.inf]),
            np.array([3.0, np.nan, np.nan, np.inf]),
            np.array([5.0, 3.0, np.nan, np.inf]),
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            median, metrics = simulation._evaluate_median(
                observations, simulations, 0
            )
        assert median[0] == 3.0
        assert median[1] == 2.0
        assert np.isnan(median[2])
        assert np.isnan(median[3])
        assert isinstance(metrics, dict)
