"""Per-catchment model validation tests.

These tests verify that:
1. Models produce valid output for all catchments
2. GR4J beats trivial baselines (mean, median) - has good defaults
3. Snow models improve GR4J simulation on snow catchments
4. GR4J with snow beats day-of-year baselines

Note: Bucket model tests only verify valid output since its default
parameters require calibration to beat baselines.
"""

from datetime import datetime, timedelta

import numpy as np
import polars as pl
import pytest

from holmes import data
from holmes.exceptions import HolmesDataError
from holmes.models import hydro, snow
from holmes.models.utils import evaluate

# Available catchments
CATCHMENTS = ["Au Saumon", "Baskatong", "Leaf"]
SNOW_CATCHMENTS = ["Au Saumon", "Baskatong"]
HYDRO_MODELS = ["gr4j", "bucket"]


def load_catchment_data(catchment: str) -> dict:
    """Load data and metadata for a catchment using available dates."""
    # Get available date range for this catchment
    available = data.get_available_catchments()
    for name, _, (start, end) in available:
        if name == catchment:
            break
    else:
        raise ValueError(f"Catchment {catchment} not found")

    # Use a 5-year window if available, otherwise use full range
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    target_start = end_dt - timedelta(days=5 * 365)
    if target_start < start_dt:
        target_start = start_dt
    start_str = target_start.strftime("%Y-%m-%d")

    catchment_data = data.read_data(catchment, start_str, end)

    result = {
        "precipitation": catchment_data["precipitation"].to_numpy(),
        "pet": catchment_data["pet"].to_numpy(),
        "observations": catchment_data["streamflow"].to_numpy(),
        "day_of_year": (
            catchment_data.select(
                (pl.col("date").dt.ordinal_day() - 1).mod(365) + 1
            )["date"]
            .to_numpy()
            .astype(np.uintp)
        ),
    }

    # Temperature is optional (only for snow catchments)
    if "temperature" in catchment_data.columns:
        result["temperature"] = catchment_data["temperature"].to_numpy()
    else:
        result["temperature"] = None

    # Load CemaNeige info if available
    try:
        cemaneige_info = data.read_cemaneige_info(catchment)
        result["elevation_layers"] = np.array(
            cemaneige_info["altitude_layers"]
        )
        result["median_elevation"] = cemaneige_info["median_altitude"]
        result["qnbv"] = cemaneige_info["qnbv"]
    except (FileNotFoundError, HolmesDataError):
        result["elevation_layers"] = None
        result["median_elevation"] = None
        result["qnbv"] = None

    return result


def run_hydro_simulation(model: str, catchment_data: dict) -> np.ndarray:
    """Run hydro model simulation with default parameters."""
    simulate = hydro.get_model(model)  # type: ignore[arg-type]
    config = hydro.get_config(model)  # type: ignore[arg-type]
    params = np.array([p["default"] for p in config])
    return simulate(
        params, catchment_data["precipitation"], catchment_data["pet"]
    )


def run_snow_hydro_simulation(
    hydro_model: str, catchment_data: dict
) -> np.ndarray:
    """Run snow + hydro model simulation with default parameters."""
    snow_simulate = snow.get_model("cemaneige")
    hydro_simulate = hydro.get_model(hydro_model)  # type: ignore[arg-type]
    hydro_config = hydro.get_config(hydro_model)  # type: ignore[arg-type]
    hydro_params = np.array([p["default"] for p in hydro_config])
    snow_params = np.array([0.25, 3.74, catchment_data["qnbv"]])
    effective_precip = snow_simulate(
        snow_params,
        catchment_data["precipitation"],
        catchment_data["temperature"],
        catchment_data["day_of_year"],
        catchment_data["elevation_layers"],
        catchment_data["median_elevation"],
    )
    return hydro_simulate(
        hydro_params, effective_precip, catchment_data["pet"]
    )


def calculate_mean_baseline_nse(_: np.ndarray) -> float:
    """NSE for predicting mean = 0 by definition."""
    return 0.0


def calculate_median_baseline_nse(observations: np.ndarray) -> float:
    """NSE for predicting median."""
    obs_mean = np.mean(observations)
    obs_median = np.median(observations)
    numerator = np.sum((observations - obs_median) ** 2)
    denominator = np.sum((observations - obs_mean) ** 2)
    return 1.0 - numerator / denominator


def calculate_doy_mean_baseline_nse(
    observations: np.ndarray, day_of_year: np.ndarray
) -> float:
    """NSE for predicting day-of-year mean."""
    obs_mean = np.mean(observations)
    doy_means = np.zeros_like(observations)
    for doy in range(1, 367):
        mask = day_of_year == doy
        if np.any(mask):
            doy_means[mask] = np.mean(observations[mask])
    numerator = np.sum((observations - doy_means) ** 2)
    denominator = np.sum((observations - obs_mean) ** 2)
    return 1.0 - numerator / denominator


def calculate_doy_median_baseline_nse(
    observations: np.ndarray, day_of_year: np.ndarray
) -> float:
    """NSE for predicting day-of-year median."""
    obs_mean = np.mean(observations)
    doy_medians = np.zeros_like(observations)
    for doy in range(1, 367):
        mask = day_of_year == doy
        if np.any(mask):
            doy_medians[mask] = np.median(observations[mask])
    numerator = np.sum((observations - doy_medians) ** 2)
    denominator = np.sum((observations - obs_mean) ** 2)
    return 1.0 - numerator / denominator


class TestModelProducesValidOutput:
    """Tests that all models produce valid output for all catchments."""

    @pytest.mark.parametrize("catchment", CATCHMENTS)
    @pytest.mark.parametrize("model", HYDRO_MODELS)
    def test_model_output_valid(self, catchment, model):
        """Model output should be non-negative with correct length."""
        catchment_data = load_catchment_data(catchment)
        simulation = run_hydro_simulation(model, catchment_data)
        assert len(simulation) == len(catchment_data["observations"])
        assert np.all(simulation >= 0)
        assert not np.any(np.isnan(simulation))


class TestGR4JBeatsBaselines:
    """Tests that GR4J beats trivial baselines (has good default params)."""

    @pytest.mark.parametrize("catchment", SNOW_CATCHMENTS)
    def test_gr4j_beats_mean_baseline(self, catchment):
        """GR4J NSE should be better than predicting catchment mean."""
        catchment_data = load_catchment_data(catchment)
        simulation = run_hydro_simulation("gr4j", catchment_data)
        model_nse = evaluate(
            catchment_data["observations"], simulation, "nse", "none"
        )
        mean_nse = calculate_mean_baseline_nse(catchment_data["observations"])
        assert (
            model_nse > mean_nse
        ), f"GR4J on {catchment}: NSE {model_nse:.4f} <= mean baseline {mean_nse:.4f}"

    @pytest.mark.parametrize("catchment", SNOW_CATCHMENTS)
    def test_gr4j_beats_median_baseline(self, catchment):
        """GR4J NSE should be better than predicting catchment median."""
        catchment_data = load_catchment_data(catchment)
        simulation = run_hydro_simulation("gr4j", catchment_data)
        model_nse = evaluate(
            catchment_data["observations"], simulation, "nse", "none"
        )
        median_nse = calculate_median_baseline_nse(
            catchment_data["observations"]
        )
        assert (
            model_nse > median_nse
        ), f"GR4J on {catchment}: NSE {model_nse:.4f} <= median baseline {median_nse:.4f}"


class TestSnowModelImprovement:
    """Tests that snow models improve GR4J simulation on snow catchments."""

    @pytest.mark.parametrize("catchment", SNOW_CATCHMENTS)
    def test_snow_model_improves_gr4j(self, catchment):
        """Adding CemaNeige should improve GR4J NSE."""
        catchment_data = load_catchment_data(catchment)
        # Run without snow
        no_snow_simulation = run_hydro_simulation("gr4j", catchment_data)
        no_snow_nse = evaluate(
            catchment_data["observations"], no_snow_simulation, "nse", "none"
        )
        # Run with snow
        snow_simulation = run_snow_hydro_simulation("gr4j", catchment_data)
        snow_nse = evaluate(
            catchment_data["observations"], snow_simulation, "nse", "none"
        )
        assert (
            snow_nse > no_snow_nse
        ), f"GR4J on {catchment}: snow NSE {snow_nse:.4f} <= no-snow NSE {no_snow_nse:.4f}"

    @pytest.mark.parametrize("catchment", SNOW_CATCHMENTS)
    def test_gr4j_snow_beats_doy_mean(self, catchment):
        """GR4J with snow should beat day-of-year mean baseline."""
        catchment_data = load_catchment_data(catchment)
        simulation = run_snow_hydro_simulation("gr4j", catchment_data)
        model_nse = evaluate(
            catchment_data["observations"], simulation, "nse", "none"
        )
        doy_mean_nse = calculate_doy_mean_baseline_nse(
            catchment_data["observations"], catchment_data["day_of_year"]
        )
        assert (
            model_nse > doy_mean_nse
        ), f"GR4J on {catchment}: snow NSE {model_nse:.4f} <= DOY mean baseline {doy_mean_nse:.4f}"

    @pytest.mark.parametrize("catchment", SNOW_CATCHMENTS)
    def test_gr4j_snow_beats_doy_median(self, catchment):
        """GR4J with snow should beat day-of-year median baseline."""
        catchment_data = load_catchment_data(catchment)
        simulation = run_snow_hydro_simulation("gr4j", catchment_data)
        model_nse = evaluate(
            catchment_data["observations"], simulation, "nse", "none"
        )
        doy_median_nse = calculate_doy_median_baseline_nse(
            catchment_data["observations"], catchment_data["day_of_year"]
        )
        assert (
            model_nse > doy_median_nse
        ), f"GR4J on {catchment}: snow NSE {model_nse:.4f} <= DOY median baseline {doy_median_nse:.4f}"
