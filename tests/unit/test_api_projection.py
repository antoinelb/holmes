import asyncio
from datetime import date
from typing import Any
from unittest.mock import AsyncMock

import holmes_rs
import numpy as np
import polars as pl
import pytest

import holmes.api_projection as projection
import holmes.data.hydro
import holmes.data.projection
import holmes.model

gr4j_defaults = list(holmes_rs.hydro.gr4j.init()[0])

valid_msg = {
    "type": "projection_data",
    "station": "061004",
    "start": "2016-01-01",
    "end": "2016-12-31",
    "method": "ministry_grid",
    "hydroModels": ["gr4j"],
    "snowModel": "none",
    "climateModel": "ClimEx",
    "scenario": "rcp8.5",
    "horizon": "2020-2049",
    "requestId": 11,
    "warmupYears": 1,
    "n_stations": 3,
    "hydroParams": {"gr4j": gr4j_defaults},
}


@pytest.fixture
def members_df(projection_df, stations_df) -> pl.DataFrame:
    # the filtered frame _load_projection builds: product rows joined with
    # the station's latitude and elevation bands, kept to 3 years for speed
    return projection_df.filter(
        (pl.col("id") == "061004") & (pl.col("datetime") < date(2023, 1, 1))
    ).join(stations_df.select("id", "lat", "elevation_layers"), on="id")


class TestHandleProjectionMessage:
    async def test_dispatches_data(self, monkeypatch, fake_ws):
        mock = AsyncMock()
        monkeypatch.setattr(projection, "_handle_data", mock)
        await projection.handle_projection_message(
            fake_ws, {"type": "projection_data"}
        )
        mock.assert_awaited_once()

    async def test_other_types_are_ignored(self, fake_ws):
        await projection.handle_projection_message(fake_ws, {"type": "bogus"})
        assert fake_ws.sent == []


class TestHandleData:
    @pytest.mark.parametrize(
        ["overrides", "match"],
        [
            ({"station": "999"}, "Unknown station"),
            ({"method": "bogus"}, "Unknown weather method"),
            ({"start": "x"}, "Invalid simulation period"),
            ({"n_stations": 0}, "Invalid number of nearest stations"),
            ({"hydroModels": "gr4j"}, "Unknown hydro model"),
            ({"hydroModels": []}, "Unknown hydro model"),
            ({"hydroModels": ["bogus"]}, "Unknown hydro model"),
            ({"snowModel": "bogus"}, "Unknown snow model"),
            ({"climateModel": 3}, "Invalid climate model"),
            ({"climateModel": ""}, "Invalid climate model"),
            ({"scenario": ""}, "Invalid scenario"),
            ({"horizon": "2100-2129"}, "Unknown horizon"),
            ({"requestId": None}, "Invalid numeric projection field"),
            ({"warmupYears": -1}, "Invalid numeric projection field"),
            ({"hydroParams": []}, "Invalid hydro parameters"),
            (
                {"hydroParams": {}},
                "Invalid hydro parameters for gr4j",
            ),
            (
                {"snowModel": "cemaneige", "snowParams": None},
                "Invalid snow parameters",
            ),
        ],
    )
    async def test_validation_errors(self, fake_ws, overrides, match):
        await projection._handle_data(fake_ws, {**valid_msg, **overrides})
        assert fake_ws.sent[0]["type"] == "error"
        assert match in fake_ws.sent[0]["data"]

    async def test_supersedes_pending_run(self, monkeypatch, fake_ws):
        monkeypatch.setattr(projection, "_load_projection", AsyncMock())
        pending = asyncio.create_task(asyncio.Event().wait())
        await asyncio.sleep(0)
        fake_ws.state.projection_task = pending
        await projection._handle_data(fake_ws, valid_msg)
        assert pending.cancelled() or pending.cancelling()
        await fake_ws.state.projection_task


class TestLoadProjection:
    @staticmethod
    async def run(fake_ws, **overrides):
        args: dict[str, Any] = {
            "station": "061004",
            "start": "2016-01-01",
            "end": "2016-12-31",
            "method": "ministry_grid",
            "n_stations": 3,
            "hydro_models": ["gr4j"],
            "snow_model": None,
            "hydro_params": {"gr4j": gr4j_defaults},
            "snow_params": None,
            "climate_model": "ClimEx",
            "scenario": "rcp8.5",
            "horizon": "2020-2049",
            "warmup_years": 1,
            "request_id": 11,
        }
        args.update(overrides)
        await projection._load_projection(fake_ws, **args)

    @pytest.fixture
    def stations(self, monkeypatch, stations_df):
        monkeypatch.setattr(
            holmes.data.hydro,
            "get_station_data",
            AsyncMock(return_value=stations_df),
        )

    async def test_missing_data_refuses(self, monkeypatch, fake_ws, stations):
        monkeypatch.setattr(
            holmes.data.projection, "has_projection_data", lambda s: False
        )
        await self.run(fake_ws)
        reply = fake_ws.sent[0]
        assert reply["type"] == "projection_error"
        assert "holmes download" in reply["data"]["message"]

    async def test_unknown_ensemble_filter_is_empty(
        self, monkeypatch, fake_ws, stations, projection_df
    ):
        monkeypatch.setattr(
            holmes.data.projection, "has_projection_data", lambda s: True
        )
        monkeypatch.setattr(
            projection,
            "_get_projection_data",
            AsyncMock(return_value=projection_df),
        )
        await self.run(fake_ws, climate_model="Nope")
        reply = fake_ws.sent[0]
        assert reply["type"] == "projection_error"
        assert "No projection data" in reply["data"]["message"]

    async def test_failure_sends_error(self, monkeypatch, fake_ws, stations):
        monkeypatch.setattr(
            holmes.data.projection, "has_projection_data", lambda s: True
        )
        monkeypatch.setattr(
            projection,
            "_get_projection_data",
            AsyncMock(side_effect=RuntimeError("boom")),
        )
        await self.run(fake_ws)
        reply = fake_ws.sent[0]
        assert reply["type"] == "projection_error"
        assert "Failed to run projection" in reply["data"]["message"]


class TestGetProjectionData:
    async def test_memoises_per_station(self, monkeypatch, projection_df):
        read = AsyncMock(return_value=projection_df)
        monkeypatch.setattr(
            holmes.data.projection, "read_projection_data", read
        )
        stations = pl.DataFrame({"id": ["061004"]})
        first = await projection._get_projection_data("061004", stations)
        second = await projection._get_projection_data("061004", stations)
        assert first is second
        read.assert_awaited_once()


class TestRunEnsemble:
    def test_members_and_medians(self, members_df):
        results, median = projection._run_ensemble(
            members_df,
            ["gr4j"],
            None,
            {"gr4j": gr4j_defaults},
            None,
            2021,
            2022,
            ("061004", "ClimEx", "rcp8.5"),
        )
        model = results["gr4j"]
        assert set(model["members"]) == {
            "historical-r1-r1i1p1",
            "historical-r2-r2i1p1",
        }
        member = model["members"]["historical-r1-r1i1p1"]
        assert len(member["regime"]) == 365
        assert set(member["indicators"]) == {
            "winter_min",
            "spring_max",
            "summer_min",
            "autumn_max",
            "mean",
        }
        assert len(model["medianRegime"]) == 365
        assert len(median["regime"]) == 365


class TestSimulateMembers:
    @pytest.fixture
    def members(self, members_df) -> list[pl.DataFrame]:
        return projection._with_calendar(members_df).partition_by(
            "member", maintain_order=True
        )

    def test_caches_by_key(self, monkeypatch, members):
        calls: list[str] = []
        real = holmes.model.simulate

        def counting(frame, *args, **kwargs):
            calls.append(frame[0, "member"])
            return real(frame, *args, **kwargs)

        monkeypatch.setattr(holmes.model, "simulate", counting)
        scope = ("061004", "ClimEx", "rcp8.5")
        first = projection._simulate_members(
            members, "gr4j", None, gr4j_defaults, None, scope
        )
        second = projection._simulate_members(
            members, "gr4j", None, gr4j_defaults, None, scope
        )
        assert first is second
        assert len(calls) == 2

    def test_fifo_eviction(self, monkeypatch, members):
        for i in range(projection.max_cached_ensembles):
            projection._simulation_cache[("dummy", i)] = {}
        projection._simulate_members(
            members,
            "gr4j",
            None,
            gr4j_defaults,
            None,
            ("061004", "ClimEx", "rcp8.5"),
        )
        assert (
            len(projection._simulation_cache)
            == projection.max_cached_ensembles
        )
        assert ("dummy", 0) not in projection._simulation_cache


class TestRunHistorical:
    def test_excludes_the_warmup_lead(self, joined_df):
        observed = joined_df.filter(pl.col("id") == "061004").sort("datetime")
        historical = projection._run_historical(
            observed,
            ["gr4j"],
            None,
            {"gr4j": gr4j_defaults},
            None,
            date(2016, 1, 1),
            date(2017, 12, 31),
        )
        assert len(historical["regime"]) == 365
        assert historical["indicators"]["mean"] is not None


class TestAggregate:
    @staticmethod
    def make_frame(days: int) -> pl.DataFrame:
        dates = pl.date_range(
            date(2021, 1, 1),
            date(2021, 1, 1) + pl.duration(days=days - 1),
            eager=True,
        )
        return pl.DataFrame(
            {"datetime": dates, "simulation": np.arange(days) * 1.0}
        )

    def test_short_record_raises(self):
        frame = pl.DataFrame(
            {
                "datetime": pl.date_range(
                    date(2021, 1, 1), date(2021, 4, 10), eager=True
                )
            }
        ).with_columns(pl.lit(1.0).alias("simulation"))
        with pytest.raises(RuntimeError, match="365 regime days"):
            projection._aggregate(frame, 2021, 2021)

    def test_seasonal_indicators(self):
        dates = pl.date_range(date(2021, 1, 1), date(2022, 12, 31), eager=True)
        frame = pl.DataFrame({"datetime": dates}).with_columns(
            pl.col("datetime").dt.month().cast(pl.Float64).alias("simulation")
        )
        regime, indicators = projection._aggregate(frame, 2021, 2022)
        assert regime.shape == (365,)
        # the simulated value equals the month number
        assert indicators["winter_min"] == 1.0
        assert indicators["spring_max"] == 6.0
        assert indicators["summer_min"] == 7.0
        assert indicators["autumn_max"] == 11.0
        assert indicators["mean"] == pytest.approx(6.52, abs=0.01)

    def test_partial_edge_year_is_dropped(self):
        dates = pl.date_range(date(2021, 1, 1), date(2022, 3, 1), eager=True)
        frame = pl.DataFrame({"datetime": dates}).with_columns(
            pl.col("datetime").dt.year().cast(pl.Float64).alias("simulation")
        )
        regime, indicators = projection._aggregate(frame, 2021, 2022)
        # 2022 has only 60 days, so the regime is 2021 alone
        assert np.allclose(regime, 2021.0)


class TestWithCalendar:
    def test_leap_day_collapses(self):
        frame = pl.DataFrame(
            {
                "datetime": [
                    date(2020, 2, 28),
                    date(2020, 2, 29),
                    date(2020, 3, 1),
                ]
            }
        )
        calendar = projection._with_calendar(frame)
        assert calendar["day_of_year"].to_list() == [59, 59, 60]
        assert calendar["year"].to_list() == [2020, 2020, 2020]


class TestMedianRegime:
    def test_skips_non_finite(self):
        regimes = [
            np.array([1.0, np.nan, np.inf]),
            np.array([3.0, 2.0, np.inf]),
            np.array([5.0, 4.0, np.inf]),
        ]
        median = projection._median_regime(regimes)
        assert median[0] == 3.0
        assert median[1] == 3.0
        assert np.isnan(median[2])


class TestMedianIndicators:
    def test_skips_non_finite(self):
        indicators = [
            {"mean": 1.0, "spring_max": np.inf},
            {"mean": 3.0, "spring_max": 2.0},
        ]
        median = projection._median_indicators(indicators)
        assert median["mean"] == 2.0
        assert median["spring_max"] == 2.0


class TestRounding:
    def test_round_keeps_none(self):
        assert projection._round([None, 1.23456789]) == [None, 1.2346]

    def test_round_indicators_nulls_non_finite(self):
        assert projection._round_indicators(
            {"a": 1.23456789, "b": float("inf"), "c": float("nan")}
        ) == {"a": 1.2346, "b": None, "c": None}


class TestSeriesPayload:
    def test_shape(self):
        payload = projection._series_payload(
            np.array([1.0, 2.0]), {"mean": 1.5}
        )
        assert payload == {
            "regime": [1.0, 2.0],
            "indicators": {"mean": 1.5},
        }
