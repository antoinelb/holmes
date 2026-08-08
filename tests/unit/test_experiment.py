import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import altair as alt
import holmes_rs
import numpy as np
import polars as pl
import pytest

import holmes.data.hydro
import holmes.data.weather
import holmes.experiment as experiment
import holmes.model

gr4j_defaults = holmes_rs.hydro.gr4j.init()[0]


def make_experiment(**overrides) -> experiment.Experiment:
    settings = {
        "calibration_station": "station 061004",
        "simulation_station": "station 061004",
        "calibration_period": (date(2016, 1, 1), date(2016, 12, 31)),
        "simulation_period": (date(2017, 1, 1), date(2017, 12, 31)),
        "hydro_model": "gr4j",
        "weather_method": "ministry_grid",
        "objective": "rmse",
        "transformation": "none",
        "warmup_years": 1,
        "with_cemaneige": False,
    }
    settings.update(overrides)
    return experiment.Experiment(**settings)


class TestReadData:
    async def test_cache_hit(self, tmp_data_dir, joined_df):
        path = tmp_data_dir / "raw" / "data_ministry_grid.ipc"
        path.parent.mkdir(parents=True)
        joined_df.write_ipc(path)
        data = await experiment.read_data()
        assert data.equals(joined_df)

    async def test_joins_weather_left(
        self,
        tmp_data_dir,
        monkeypatch,
        stations_df,
        weather_df,
        streamflow_df,
    ):
        (tmp_data_dir / "raw").mkdir(parents=True)
        monkeypatch.setattr(
            holmes.data.hydro,
            "get_station_data",
            AsyncMock(return_value=stations_df),
        )
        # a shortened streamflow record leaves weather-only days behind
        short = streamflow_df.filter(pl.col("datetime") < date(2017, 1, 1))

        async def get_streamflow_data(id):
            return short.filter(pl.col("id") == id)

        monkeypatch.setattr(
            holmes.data.hydro, "get_streamflow_data", get_streamflow_data
        )
        monkeypatch.setattr(
            holmes.data.weather,
            "read_weather_data",
            lambda stations, method, n_stations: weather_df,
        )
        data = await experiment.read_data()
        assert data.height == weather_df.height
        late = data.filter(pl.col("datetime") >= date(2017, 1, 1))
        assert late["streamflow"].null_count() == late.height
        assert (tmp_data_dir / "raw" / "data_ministry_grid.ipc").exists()

    async def test_nearest_stations_cache_carries_n(
        self, tmp_data_dir, joined_df
    ):
        path = tmp_data_dir / "raw" / "data_nearest_stations_4.ipc"
        path.parent.mkdir(parents=True)
        joined_df.write_ipc(path)
        data = await experiment.read_data(
            weather_method="nearest_stations", n_stations=4
        )
        assert data.equals(joined_df)


class TestFilterWithWarmup:
    def test_full_lead(self, joined_df):
        filtered, warmup = experiment._filter_with_warmup(
            joined_df,
            "station 061004",
            (date(2016, 1, 1), date(2016, 12, 31)),
            1,
        )
        assert warmup == 365
        assert filtered["datetime"].min() == date(2015, 1, 1)
        assert filtered["datetime"].max() == date(2016, 12, 31)

    def test_lead_clamps_to_record_start(self, joined_df):
        filtered, warmup = experiment._filter_with_warmup(
            joined_df,
            "station 061004",
            (date(2016, 1, 1), date(2016, 12, 31)),
            3,
        )
        # the record starts 2015-01-01, so only one year of lead exists
        assert warmup == 365
        assert filtered["datetime"].min() == date(2015, 1, 1)


class TestUpdateExperimentList:
    def test_creates_and_sorts_registry(self, tmp_data_dir):
        first = make_experiment()
        second = make_experiment(objective="kge")
        path_1, hash_1 = experiment._update_experiment_list(first)
        path_2, hash_2 = experiment._update_experiment_list(second)
        assert hash_1 != hash_2
        assert path_1.name == hash_1
        registry_path = (
            tmp_data_dir / "results" / "experiments" / "experiments.json"
        )
        with open(registry_path) as f:
            registry = json.load(f)
        assert list(registry) == sorted([hash_1, hash_2])

    def test_existing_hash_is_not_rewritten(self, tmp_data_dir):
        config = make_experiment()
        _, hash_ = experiment._update_experiment_list(config)
        registry_path = (
            tmp_data_dir / "results" / "experiments" / "experiments.json"
        )
        before = registry_path.read_text()
        _, again = experiment._update_experiment_list(config)
        assert again == hash_
        assert registry_path.read_text() == before


class TestRunSubexperiment:
    @pytest.fixture
    def fast_fig(self, monkeypatch):
        fig = MagicMock()
        monkeypatch.setattr(experiment, "_create_timeseries_fig", fig)
        return fig

    def make_results_dir(self, tmp_data_dir) -> Path:
        path = tmp_data_dir / "results" / "experiments" / "abc" / "gr4j"
        path.mkdir(parents=True)
        return path

    async def test_cached_artifacts_return_early(
        self, tmp_data_dir, joined_df
    ):
        path = self.make_results_dir(tmp_data_dir)
        cached = pl.DataFrame({"calibration_rmse": [1.0]})
        cached.write_csv(path / "results.csv")
        (path / "calibration.svg").touch()
        (path / "simulation.svg").touch()
        results = await experiment._run_subexperiment(
            joined_df, make_experiment(), "abc", path
        )
        assert results.equals(cached)

    async def test_cached_params_skip_calibration(
        self, tmp_data_dir, monkeypatch, joined_df, fast_fig
    ):
        path = self.make_results_dir(tmp_data_dir)
        with open(path / "params.json", "w") as f:
            json.dump({"hydro": list(gr4j_defaults), "snow": None}, f)
        calibrate = AsyncMock(side_effect=AssertionError("must not run"))
        monkeypatch.setattr(holmes.model, "calibrate", calibrate)
        results = await experiment._run_subexperiment(
            joined_df, make_experiment(), "abc", path
        )
        assert "calibration_rmse" in results.columns
        assert "simulation_kge_jja" in results.columns
        assert (path / "results.csv").exists()
        assert fast_fig.call_count == 2

    async def test_calibrates_and_writes_params(
        self, tmp_data_dir, monkeypatch, joined_df, fast_fig
    ):
        path = self.make_results_dir(tmp_data_dir)
        calibrate = AsyncMock(
            return_value=(gr4j_defaults, np.array([0.25, 3.74, 300.0]))
        )
        monkeypatch.setattr(holmes.model, "calibrate", calibrate)
        settings = make_experiment(with_cemaneige=True)
        await experiment._run_subexperiment(joined_df, settings, "abc", path)
        calibrate.assert_awaited_once()
        with open(path / "params.json") as f:
            params = json.load(f)
        assert params["hydro"] == pytest.approx(list(gr4j_defaults))

    async def test_snow_params_round_trip(
        self, tmp_data_dir, monkeypatch, joined_df, fast_fig
    ):
        path = self.make_results_dir(tmp_data_dir)
        with open(path / "params.json", "w") as f:
            json.dump(
                {"hydro": list(gr4j_defaults), "snow": [0.25, 3.74, 300.0]},
                f,
            )
        results = await experiment._run_subexperiment(
            joined_df, make_experiment(with_cemaneige=True), "abc", path
        )
        assert "simulation_rmse" in results.columns


class TestRunExperiment:
    async def test_all_fans_out_over_models(
        self, tmp_data_dir, monkeypatch, joined_df
    ):
        sub = AsyncMock(return_value=pl.DataFrame({"rmse": [1.0]}))
        monkeypatch.setattr(experiment, "_run_subexperiment", sub)
        await experiment._run_experiment(
            joined_df, make_experiment(hydro_model="all")
        )
        from typing import get_args

        assert sub.await_count == len(get_args(holmes.model.HydroModel))

    async def test_all_with_cached_results_skips(
        self, tmp_data_dir, monkeypatch, joined_df
    ):
        settings = make_experiment(hydro_model="all")
        path, _ = experiment._update_experiment_list(settings)
        path.mkdir(exist_ok=True, parents=True)
        pl.DataFrame({"rmse": [1.0]}).write_csv(path / "results.csv")
        sub = AsyncMock(side_effect=AssertionError("must not run"))
        monkeypatch.setattr(experiment, "_run_subexperiment", sub)
        await experiment._run_experiment(joined_df, settings)

    async def test_single_model(self, tmp_data_dir, monkeypatch, joined_df):
        sub = AsyncMock(return_value=pl.DataFrame({"rmse": [1.0]}))
        monkeypatch.setattr(experiment, "_run_subexperiment", sub)
        await experiment._run_experiment(joined_df, make_experiment())
        sub.assert_awaited_once()


class TestRunExperimentEntry:
    async def test_reads_and_runs_each_experiment(
        self, monkeypatch, joined_df
    ):
        read = AsyncMock(return_value=joined_df)
        monkeypatch.setattr(experiment, "read_data", read)
        figs = MagicMock()
        monkeypatch.setattr(experiment, "_create_timeseries_figs", figs)
        run = AsyncMock()
        monkeypatch.setattr(experiment, "_run_experiment", run)
        await experiment.run_experiment()
        figs.assert_called_once()
        assert run.await_count == 4
        assert read.await_count == 5


class TestCreateTimeseriesFigs:
    def test_skips_existing_figures(
        self, tmp_data_dir, monkeypatch, joined_df
    ):
        calls: list[Path] = []
        monkeypatch.setattr(
            experiment,
            "_create_timeseries_fig",
            lambda data, path: calls.append(path),
        )
        existing = (
            tmp_data_dir
            / "results"
            / "catchments"
            / "061004_station_061004.svg"
        )
        existing.parent.mkdir(parents=True)
        existing.touch()
        experiment._create_timeseries_figs(joined_df)
        assert [path.name for path in calls] == ["061020_station_061020.svg"]


class TestCreateTimeseriesFig:
    @pytest.fixture
    def figure_data(self, joined_df) -> pl.DataFrame:
        data = (
            joined_df.filter(pl.col("id") == "061004")
            .head(60)
            .with_columns(pl.col("datetime").cast(pl.Datetime("us")))
        )
        # one isolated missing day and one multi-day run exercise both
        # missing marks
        return data.with_columns(
            pl.when(pl.arange(0, data.height).is_in([5, 20, 21, 22]))
            .then(None)
            .otherwise(pl.col("streamflow"))
            .alias("streamflow")
        )

    def test_with_simulation_saves_svg(self, tmp_path, figure_data):
        data = figure_data.with_columns(
            pl.col("streamflow").fill_null(1.0).alias("simulation")
        )
        path = tmp_path / "figures" / "simulation.svg"
        experiment._create_timeseries_fig(data, path)
        assert path.exists()
        assert path.read_bytes().startswith(b"<svg")

    def test_without_simulation(self, tmp_path, monkeypatch, figure_data):
        saved: list[Path] = []
        monkeypatch.setattr(
            alt.VConcatChart, "save", lambda self, path: saved.append(path)
        )
        experiment._create_timeseries_fig(
            figure_data, tmp_path / "observed.svg"
        )
        assert saved == [tmp_path / "observed.svg"]
