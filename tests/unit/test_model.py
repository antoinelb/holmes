import threading
from datetime import date
from typing import get_args

import holmes_rs
import numpy as np
import polars as pl
import pytest

from holmes.model import (
    HydroModel,
    _evaluate_objectives,
    _fill_missing,
    _get_hydro_model,
    _get_pet_model,
    _get_snow_model,
    _penalize_degenerate,
    _prepare_data,
    calculate_qnbv,
    calibrate,
    calibrate_stream,
    evaluate_simulation,
    evaluate_simulation_metrics,
    get_config,
    simulate,
    simulate_manual,
    simulate_with_metrics,
    warmup_start,
)

fast_sce = {
    "seed": 0,
    "n_complexes": 2,
    "k_stop": 1,
    "p_convergence_threshold": 0.5,
    "geometric_range_threshold": 0.5,
    "max_evaluations": 60,
}

gr4j_defaults = holmes_rs.hydro.gr4j.init()[0]


@pytest.fixture(scope="module")
def model_data(joined_df: pl.DataFrame) -> pl.DataFrame:
    return joined_df.filter(pl.col("id") == "061004").sort("datetime")


class TestGetConfig:
    def test_sce_parameters(self):
        config = get_config("sce")
        assert [param["name"] for param in config] == [
            "seed",
            "n_complexes",
            "k_stop",
            "p_convergence_threshold",
            "geometric_range_threshold",
            "max_evaluations",
        ]


class TestCalibrate:
    async def test_without_snow(self, model_data):
        hydro_params, snow_params = await calibrate(
            model_data,
            "gr4j",
            "rmse",
            None,
            "none",
            0,
            params=fast_sce,
        )
        assert hydro_params.shape == (4,)
        assert snow_params is None

    async def test_with_snow(self, model_data):
        hydro_params, snow_params = await calibrate(
            model_data,
            "gr4j",
            "rmse",
            "cemaneige",
            "none",
            365,
            params=fast_sce,
        )
        assert hydro_params.shape == (4,)
        assert snow_params is not None
        assert snow_params[:2].tolist() == [0.25, 3.74]
        assert snow_params[2] > 0


class TestCalibrateStream:
    def test_callback_streams_steps(self, model_data):
        steps: list[tuple[int, bool]] = []

        def callback(step_i, done, params, simulation, objectives):
            steps.append((step_i, done))
            assert simulation.shape == (model_data.height,)
            assert objectives.shape == (3,)

        calibrate_stream(
            model_data,
            "gr4j",
            "rmse",
            None,
            "none",
            0,
            params=fast_sce,
            callback=callback,
        )
        assert [step for step, _ in steps] == list(range(len(steps)))
        assert steps[-1][1] is True

    def test_stop_event_interrupts(self, model_data):
        stop_event = threading.Event()
        calls: list[int] = []

        def callback(step_i, done, params, simulation, objectives):
            calls.append(step_i)
            stop_event.set()

        params = {**fast_sce, "max_evaluations": 50000, "k_stop": 100}
        calibrate_stream(
            model_data,
            "gr4j",
            "rmse",
            None,
            "none",
            0,
            params=params,
            callback=callback,
            stop_event=stop_event,
        )
        assert calls == [0]

    def test_default_params(self, model_data):
        # the defaults run a full SCE, so give it a two-month record
        hydro_params, _ = calibrate_stream(
            model_data.slice(0, 60),
            "gr4j",
            "rmse",
            None,
            "none",
            0,
        )
        assert hydro_params.shape == (4,)


class TestSimulateManual:
    def test_without_snow(self, model_data):
        simulation, objectives = simulate_manual(
            model_data,
            "gr4j",
            None,
            "none",
            0,
            hydro_params=gr4j_defaults,
        )
        assert simulation.shape == (model_data.height,)
        assert set(objectives) == {"rmse", "nse", "kge"}
        assert np.isfinite(objectives["rmse"])

    def test_with_snow(self, model_data):
        simulation, objectives = simulate_manual(
            model_data,
            "gr4j",
            "cemaneige",
            "none",
            365,
            hydro_params=gr4j_defaults,
        )
        assert simulation.shape == (model_data.height,)
        assert np.isfinite(objectives["rmse"])


class TestSimulateWithMetrics:
    def test_returns_display_metrics(self, model_data):
        simulation, metrics = simulate_with_metrics(
            model_data,
            "gr4j",
            None,
            0,
            hydro_params=gr4j_defaults,
            snow_params=None,
        )
        assert simulation.shape == (model_data.height,)
        assert set(metrics) == {
            "kge",
            "kge_sqrt",
            "kge_log",
            "mean_bias",
            "deviation_bias",
            "correlation",
        }
        assert np.isfinite(metrics["kge"])


class TestSimulate:
    def test_without_streamflow_column(self, model_data):
        simulation = simulate(
            model_data.drop("streamflow"),
            "gr4j",
            None,
            hydro_params=gr4j_defaults,
            snow_params=None,
        )
        assert simulation.shape == (model_data.height,)
        assert np.all(np.isfinite(simulation))


class TestEvaluateSimulationMetrics:
    def test_nominal(self):
        rng = np.random.default_rng(0)
        observations = rng.gamma(2.0, 1.0, 400)
        simulation = observations * 1.1
        metrics = evaluate_simulation_metrics(observations, simulation, 30)
        assert metrics["mean_bias"] == pytest.approx(1.1)
        assert metrics["correlation"] == pytest.approx(1.0)
        assert np.isfinite(metrics["kge"])

    def test_non_finite_simulation_penalized(self):
        observations = np.ones(10)
        simulation = np.ones(10)
        simulation[5] = np.nan
        metrics = evaluate_simulation_metrics(observations, simulation, 0)
        assert all(np.isnan(value) for value in metrics.values())

    def test_all_missing_observations_penalized(self):
        observations = np.full(10, np.nan)
        simulation = np.ones(10)
        metrics = evaluate_simulation_metrics(observations, simulation, 0)
        assert all(np.isnan(value) for value in metrics.values())

    def test_negative_simulation_sinks_sqrt_only(self):
        rng = np.random.default_rng(0)
        observations = rng.gamma(2.0, 1.0, 400)
        simulation = observations.copy()
        simulation[10] = -1.0
        metrics = evaluate_simulation_metrics(observations, simulation, 0)
        assert np.isnan(metrics["kge_sqrt"])
        assert np.isfinite(metrics["kge"])


class TestEvaluateSimulation:
    def test_scores_by_season(self, model_data):
        data, metrics = evaluate_simulation(
            model_data,
            "gr4j",
            None,
            hydro_params=gr4j_defaults,
            snow_params=None,
            warmup_steps=365,
        )
        assert data.height == model_data.height - 365
        assert "simulation" in data.columns
        assert set(data["season"].unique()) == {"djf", "mam", "jja", "son"}
        for name in ["rmse", "kge"]:
            assert name in metrics.columns
            for season in ["djf", "mam", "jja", "son"]:
                assert f"{name}_{season}" in metrics.columns


class TestCalculateQnbv:
    def test_all_solid_precipitation(self):
        days = pl.date_range(
            date(2021, 1, 1), date(2022, 12, 31), eager=True
        ).alias("datetime")
        data = pl.DataFrame(
            {
                "id": ["x"] * len(days),
                "datetime": days,
                "precipitation": [2.0] * len(days),
                "temperature": [-5.0] * len(days),
            }
        )
        assert calculate_qnbv(data) == pytest.approx(730.0)

    def test_all_liquid_precipitation(self):
        days = pl.date_range(
            date(2021, 1, 1), date(2021, 12, 31), eager=True
        ).alias("datetime")
        data = pl.DataFrame(
            {
                "id": ["x"] * len(days),
                "datetime": days,
                "precipitation": [2.0] * len(days),
                "temperature": [10.0] * len(days),
            }
        )
        assert calculate_qnbv(data) == pytest.approx(0.0)


class TestWarmupStart:
    def test_nominal(self):
        assert warmup_start(date(2020, 6, 1), 3) == date(2017, 6, 1)

    def test_leap_day_clamps_to_28(self):
        assert warmup_start(date(2024, 2, 29), 1) == date(2023, 2, 28)

    def test_negative_years_raises(self):
        with pytest.raises(ValueError, match="warmup_years"):
            warmup_start(date(2020, 1, 1), -1)


class TestGetHydroModel:
    @pytest.mark.parametrize("model", get_args(HydroModel))
    def test_maps_to_holmes_rs(self, model):
        assert (
            _get_hydro_model(model) is getattr(holmes_rs.hydro, model).simulate
        )


class TestGetSnowModel:
    def test_cemaneige(self):
        assert (
            _get_snow_model("cemaneige") is holmes_rs.snow.cemaneige.simulate
        )


class TestGetPetModel:
    def test_oudin(self):
        assert _get_pet_model("oudin") is holmes_rs.pet.oudin.simulate


class TestEvaluateObjectives:
    @pytest.mark.parametrize("transformation", ["log", "sqrt", "none"])
    def test_transformations(self, transformation):
        rng = np.random.default_rng(0)
        observations = rng.gamma(2.0, 1.0, 400)
        simulation = observations * 1.1
        objectives = _evaluate_objectives(
            observations, simulation, transformation, 30
        )
        assert set(objectives) == {"rmse", "nse", "kge"}
        assert np.isfinite(objectives["rmse"])

    def test_non_finite_simulation_penalized(self):
        observations = np.ones(10)
        simulation = np.ones(10)
        simulation[3] = np.inf
        objectives = _evaluate_objectives(observations, simulation, "none", 0)
        assert objectives == {
            "rmse": np.inf,
            "nse": -np.inf,
            "kge": -np.inf,
        }

    def test_negative_simulation_with_sqrt_penalized(self):
        rng = np.random.default_rng(0)
        observations = rng.gamma(2.0, 1.0, 100)
        simulation = observations.copy()
        simulation[5] = -1.0
        with np.errstate(invalid="ignore"):
            objectives = _evaluate_objectives(
                observations, simulation, "sqrt", 0
            )
        assert objectives["rmse"] == np.inf

    def test_gaps_are_dropped_before_transform(self):
        observations = np.array([1.0, np.nan, 2.0, 3.0])
        simulation = np.array([1.0, 5.0, 2.0, 3.0])
        objectives = _evaluate_objectives(observations, simulation, "log", 0)
        # the gap row (obs NaN, sim 5.0) must not count against the score
        assert objectives["rmse"] == pytest.approx(0.0)


class TestPenalizeDegenerate:
    def test_returns_metric_value(self):
        assert (
            _penalize_degenerate(
                lambda obs, sim: 0.5, np.ones(3), np.ones(3), np.inf
            )
            == 0.5
        )

    def test_exception_maps_to_penalty(self):
        def metric(obs, sim):
            raise ValueError("degenerate")

        assert (
            _penalize_degenerate(metric, np.ones(3), np.ones(3), np.inf)
            == np.inf
        )


class TestPrepareData:
    def test_leap_day_remapped(self, model_data):
        day_of_year, _, _, _, _, _, _ = _prepare_data(
            model_data,
            pet_model="oudin",
            snow_model=None,
            snow_params=None,
        )
        # 2016 is a leap year in the record: Feb 29 collapses onto Feb 28
        # (day 59 of the non-leap 2021), and March 1 lands on day 60
        rows = model_data.with_row_index().filter(
            pl.col("datetime").is_in(
                [date(2016, 2, 28), date(2016, 2, 29), date(2016, 3, 1)]
            )
        )["index"]
        assert day_of_year[rows[0]] == 59
        assert day_of_year[rows[1]] == 59
        assert day_of_year[rows[2]] == 60

    def test_snow_without_params_raises(self, model_data):
        with pytest.raises(ValueError, match="snow_params"):
            _prepare_data(
                model_data,
                pet_model="oudin",
                snow_model="cemaneige",
                snow_params=None,
            )

    def test_snow_transforms_precipitation(self, model_data):
        _, _, _, _, _, raw, _ = _prepare_data(
            model_data,
            pet_model="oudin",
            snow_model=None,
            snow_params=None,
        )
        _, _, _, _, _, snowed, _ = _prepare_data(
            model_data,
            pet_model="oudin",
            snow_model="cemaneige",
            snow_params=np.array([0.25, 3.74, 300.0]),
        )
        assert not np.allclose(raw, snowed)

    def test_missing_streamflow_column_becomes_nan(self, model_data):
        _, _, _, observations, _, _, _ = _prepare_data(
            model_data.drop("streamflow"),
            pet_model="oudin",
            snow_model=None,
            snow_params=None,
        )
        assert np.all(np.isnan(observations))


class TestFillMissing:
    def test_isolated_null_interpolated(self):
        data = np.array([1.0, np.nan, 3.0])
        assert _fill_missing(data, "x").tolist() == [1.0, 2.0, 3.0]

    def test_adjacent_nulls_raise(self):
        data = np.array([1.0, np.nan, np.nan, 4.0])
        with pytest.raises(RuntimeError, match="more than one missing"):
            _fill_missing(data, "x")

    def test_edge_null_raises(self):
        data = np.array([np.nan, 2.0, 3.0])
        with pytest.raises(RuntimeError, match="more than one missing"):
            _fill_missing(data, "x")
