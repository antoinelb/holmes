"""Unit tests for holmes.models.calibration module."""

import asyncio

import numpy as np
import polars as pl
import pytest

from holmes import data
from holmes.models import calibration


class TestGetConfig:
    """Tests for get_config function."""

    def test_get_config_sce(self):
        """SCE algorithm config has expected structure."""
        config = calibration.get_config("sce")
        assert isinstance(config, list)
        for param in config:
            assert "name" in param
            assert "default" in param
            assert "min" in param

    def test_sce_param_names(self):
        """SCE has expected parameter names."""
        config = calibration.get_config("sce")
        names = [p["name"] for p in config]
        expected = [
            "n_complexes",
            "k_stop",
            "p_convergence_threshold",
            "geometric_range_threshold",
            "max_evaluations",
        ]
        assert names == expected

    def test_sce_integer_flags(self):
        """SCE config correctly marks integer parameters."""
        config = calibration.get_config("sce")
        for param in config:
            if param["name"] in ["n_complexes", "k_stop", "max_evaluations"]:
                assert param["integer"] is True
            else:
                assert param["integer"] is False


class TestCalibrate:
    """Tests for calibrate function."""

    @pytest.fixture
    def sample_data(self):
        """Load sample data for calibration tests."""
        catchment_data = data.read_data(
            "Au Saumon", "2000-01-01", "2001-12-31"
        )
        cemaneige_info = data.read_cemaneige_info("Au Saumon")
        return {
            "precipitation": catchment_data["precipitation"].to_numpy(),
            "temperature": catchment_data["temperature"].to_numpy(),
            "pet": catchment_data["pet"].to_numpy(),
            "observations": catchment_data["streamflow"].to_numpy(),
            "day_of_year": (
                catchment_data.select(
                    (pl.col("date").dt.ordinal_day() - 1).mod(365) + 1
                )["date"]
                .to_numpy()
                .astype(np.uintp)
            ),
            "elevation_layers": np.array(cemaneige_info["altitude_layers"]),
            "median_elevation": cemaneige_info["median_altitude"],
            "qnbv": cemaneige_info["qnbv"],
        }

    @pytest.fixture
    def sce_params(self):
        """SCE parameters for fast testing."""
        return {
            "n_complexes": 2,
            "k_stop": 2,
            "p_convergence_threshold": 0.1,
            "geometric_range_threshold": 0.001,
            "max_evaluations": 50,
        }

    @pytest.mark.asyncio
    async def test_calibrate_basic(self, sample_data, sce_params):
        """Basic calibration flow completes."""
        result = await calibration.calibrate(
            sample_data["precipitation"],
            sample_data["temperature"],
            sample_data["pet"],
            sample_data["observations"],
            sample_data["day_of_year"],
            sample_data["elevation_layers"],
            sample_data["median_elevation"],
            sample_data["qnbv"],
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            algorithm="sce",
            params=sce_params,
        )
        assert isinstance(result, np.ndarray)

    @pytest.mark.asyncio
    async def test_calibrate_with_snow(self, sample_data, sce_params):
        """Calibration with snow model completes."""
        result = await calibration.calibrate(
            sample_data["precipitation"],
            sample_data["temperature"],
            sample_data["pet"],
            sample_data["observations"],
            sample_data["day_of_year"],
            sample_data["elevation_layers"],
            sample_data["median_elevation"],
            sample_data["qnbv"],
            hydro_model="gr4j",
            snow_model="cemaneige",
            objective="nse",
            transformation="none",
            algorithm="sce",
            params=sce_params,
        )
        assert isinstance(result, np.ndarray)

    @pytest.mark.asyncio
    async def test_calibrate_stop_event(self, sample_data):
        """Calibration respects stop event."""
        stop_event = asyncio.Event()
        iterations = []

        # Use high max_evaluations to ensure calibration doesn't finish early
        sce_params_long = {
            "n_complexes": 2,
            "k_stop": 10,
            "p_convergence_threshold": 0.0001,
            "geometric_range_threshold": 0.00001,
            "max_evaluations": 10000,
        }

        async def callback(done, params, simulation, results):
            iterations.append(1)
            if len(iterations) >= 3:
                stop_event.set()

        await calibration.calibrate(
            sample_data["precipitation"],
            sample_data["temperature"],
            sample_data["pet"],
            sample_data["observations"],
            sample_data["day_of_year"],
            sample_data["elevation_layers"],
            sample_data["median_elevation"],
            sample_data["qnbv"],
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            algorithm="sce",
            params=sce_params_long,
            callback=callback,
            stop_event=stop_event,
        )
        # Should have stopped after a few iterations
        assert len(iterations) >= 3

    @pytest.mark.asyncio
    async def test_calibrate_callback(self, sample_data, sce_params):
        """Callback is invoked during calibration."""
        callback_calls = []

        async def callback(done, params, simulation, results):
            callback_calls.append(
                {
                    "done": done,
                    "params": params,
                    "simulation": simulation,
                    "results": results,
                }
            )

        stop_event = asyncio.Event()

        # Stop after a few iterations
        async def stop_after_few():
            await asyncio.sleep(0.1)
            stop_event.set()

        asyncio.create_task(stop_after_few())

        await calibration.calibrate(
            sample_data["precipitation"],
            sample_data["temperature"],
            sample_data["pet"],
            sample_data["observations"],
            sample_data["day_of_year"],
            sample_data["elevation_layers"],
            sample_data["median_elevation"],
            sample_data["qnbv"],
            hydro_model="gr4j",
            snow_model=None,
            objective="nse",
            transformation="none",
            algorithm="sce",
            params=sce_params,
            callback=callback,
            stop_event=stop_event,
        )
        assert len(callback_calls) > 0
        for call in callback_calls:
            assert "done" in call
            assert "params" in call
            assert "simulation" in call
            assert "results" in call
            assert "rmse" in call["results"]
            assert "nse" in call["results"]
            assert "kge" in call["results"]
