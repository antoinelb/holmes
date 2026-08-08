import asyncio
import threading
from datetime import date
from unittest.mock import AsyncMock

import holmes_rs
import numpy as np
import polars as pl
import pytest

import holmes.api_calibration as calibration
import holmes.experiment

gr4j_defaults = list(holmes_rs.hydro.gr4j.init()[0])

valid_data_msg = {
    "type": "calibration_data",
    "station": "061004",
    "method": "ministry_grid",
    "start": "2016-01-01",
    "end": "2016-12-31",
    "n_stations": 3,
    "warmupYears": 1,
}

valid_manual_msg = {
    "type": "calibration_manual",
    **valid_data_msg,
    "hydroModel": "gr4j",
    "snowModel": "none",
    "transformation": "none",
    "requestId": 7,
    "hydroParams": gr4j_defaults,
}

valid_start_msg = {
    "type": "calibration_start",
    **valid_data_msg,
    "hydroModels": ["gr4j"],
    "snowModel": "none",
    "objective": "rmse",
    "transformation": "none",
    "algorithm": "sce",
    "runId": 3,
    "algorithmParams": None,
}


@pytest.fixture
def joined_data(monkeypatch, joined_df):
    read = AsyncMock(return_value=joined_df)
    monkeypatch.setattr(holmes.experiment, "read_data", read)
    return read


async def parked_task() -> asyncio.Task:
    task = asyncio.create_task(asyncio.Event().wait())
    await asyncio.sleep(0)
    return task


class TestHandleCalibrationMessage:
    @pytest.mark.parametrize(
        ["type_", "handler"],
        [
            ("calibration_info", "_handle_info"),
            ("calibration_data", "_handle_data"),
            ("calibration_manual", "_handle_manual"),
            ("calibration_start", "_handle_start"),
            ("calibration_stop", "_handle_stop"),
        ],
    )
    async def test_dispatch(self, monkeypatch, fake_ws, type_, handler):
        mock = AsyncMock()
        monkeypatch.setattr(calibration, handler, mock)
        await calibration.handle_calibration_message(fake_ws, {"type": type_})
        mock.assert_awaited_once()


class TestHandleInfo:
    async def test_sends_bounds(self, fake_ws):
        await calibration._handle_info(fake_ws)
        reply = fake_ws.sent[0]
        assert reply["type"] == "calibration_info"
        assert "gr4j" in reply["data"]["hydro"]
        assert "sce" in reply["data"]["algorithms"]


class TestCleanupCalibration:
    def test_sets_every_stop(self, fake_ws):
        stops = {"gr4j": threading.Event(), "bucket": threading.Event()}
        fake_ws.state.calibration_stops = stops
        calibration.cleanup_calibration(fake_ws)
        assert all(event.is_set() for event in stops.values())

    def test_without_stops(self, fake_ws):
        calibration.cleanup_calibration(fake_ws)


class TestGetData:
    async def test_memoises_per_key(self, joined_data):
        first = await calibration.get_data("ministry_grid", 3)
        second = await calibration.get_data("ministry_grid", 3)
        assert first is second
        joined_data.assert_awaited_once()
        await calibration.get_data("ministry_grid", 4)
        assert joined_data.await_count == 2


class TestFilterData:
    def test_filters_by_id_and_dates(self, joined_df):
        filtered = calibration.filter_data(
            joined_df, "061004", "2016-01-01", "2016-12-31"
        )
        assert filtered["id"].unique().to_list() == ["061004"]
        assert filtered.height == 366
        assert filtered["datetime"].min() == date(2016, 1, 1)


class TestFilterDataWithWarmup:
    def test_prepends_the_lead(self, joined_df):
        filtered, warmup = calibration.filter_data_with_warmup(
            joined_df, "061004", "2016-01-01", "2016-12-31", 1
        )
        assert warmup == 365
        assert filtered["datetime"].min() == date(2015, 1, 1)

    def test_clamps_to_record(self, joined_df):
        filtered, warmup = calibration.filter_data_with_warmup(
            joined_df, "061004", "2015-06-01", "2015-12-31", 3
        )
        # only 151 days exist before June 1 2015
        assert warmup == 151


class TestSanitize:
    def test_values(self):
        assert calibration.sanitize(
            [1, 2.5, float("inf"), float("nan"), None, "x"]
        ) == [1.0, 2.5, None, None, None, None]

    def test_objectives(self):
        assert calibration.sanitize_objectives(
            {"rmse": 1.0, "nse": float("-inf")}
        ) == {"rmse": 1.0, "nse": None}


class TestCheckObservations:
    def test_all_null_raises(self, joined_df):
        data = joined_df.with_columns(
            pl.lit(None, dtype=pl.Float64).alias("streamflow")
        )
        with pytest.raises(ValueError, match="No streamflow observations"):
            calibration._check_observations(data)

    def test_null_warmup_only_passes(self, joined_df):
        data = joined_df.head(100)
        data = data.with_columns(
            pl.when(pl.arange(0, data.height) < 50)
            .then(None)
            .otherwise(pl.col("streamflow"))
            .alias("streamflow")
        )
        calibration._check_observations(data, warmup_steps=50)


class TestHandleData:
    @pytest.mark.parametrize(
        ["overrides", "match"],
        [
            ({"station": "999"}, "Unknown station"),
            ({"method": "bogus"}, "Unknown weather method"),
            ({"start": "not-a-date"}, "Invalid calibration date range"),
            ({"n_stations": 9}, "Invalid number of nearest stations"),
            ({"warmupYears": -1}, "Invalid number of warmup years"),
            ({"warmupYears": "x"}, "Invalid number of warmup years"),
        ],
    )
    async def test_validation_errors(self, fake_ws, overrides, match):
        await calibration._handle_data(
            fake_ws, {**valid_data_msg, **overrides}
        )
        assert fake_ws.sent[0]["type"] == "error"
        assert match in fake_ws.sent[0]["data"]

    async def test_supersedes_pending_load(self, monkeypatch, fake_ws):
        monkeypatch.setattr(calibration, "_load_data", AsyncMock())
        pending = await parked_task()
        fake_ws.state.calibration_data_task = pending
        await calibration._handle_data(fake_ws, valid_data_msg)
        assert pending.cancelled() or pending.cancelling()
        await fake_ws.state.calibration_data_task


class TestLoadData:
    async def test_echoes_request_with_qnbv(self, fake_ws, joined_data):
        await calibration._load_data(
            fake_ws,
            "061004",
            "2016-01-01",
            "2016-12-31",
            "ministry_grid",
            3,
            1,
        )
        reply = fake_ws.sent[0]
        assert reply["type"] == "calibration_data"
        assert reply["data"]["station"] == "061004"
        assert reply["data"]["warmupYears"] == 1
        assert reply["data"]["qnbv"] > 0
        assert len(reply["data"]["data"]) == 366 + 365

    async def test_failure_sends_calibration_error(self, monkeypatch, fake_ws):
        monkeypatch.setattr(
            calibration,
            "get_data",
            AsyncMock(side_effect=RuntimeError("boom")),
        )
        await calibration._load_data(
            fake_ws,
            "061004",
            "2016-01-01",
            "2016-12-31",
            "ministry_grid",
            3,
            1,
        )
        reply = fake_ws.sent[0]
        assert reply["type"] == "calibration_error"
        assert "Failed to load calibration data" in reply["data"]["message"]


class TestHandleManual:
    @pytest.mark.parametrize(
        ["overrides", "match"],
        [
            ({"station": "999"}, "Unknown station"),
            ({"method": "bogus"}, "Unknown weather method"),
            ({"end": None}, "Invalid calibration date range"),
            ({"n_stations": 0}, "Invalid number of nearest stations"),
            ({"hydroModel": "bogus"}, "Unknown hydro model"),
            ({"snowModel": "bogus"}, "Unknown snow model"),
            ({"transformation": "bogus"}, "Unknown transformation"),
            ({"warmupYears": -1}, "Invalid numeric calibration field"),
            ({"requestId": None}, "Invalid numeric calibration field"),
            ({"hydroParams": "x"}, "Invalid hydro parameters"),
            ({"hydroParams": ["a"]}, "Invalid hydro parameters"),
        ],
    )
    async def test_validation_errors(self, fake_ws, overrides, match):
        await calibration._handle_manual(
            fake_ws, {**valid_manual_msg, **overrides}
        )
        assert fake_ws.sent[0]["type"] == "error"
        assert match in fake_ws.sent[0]["data"]

    async def test_first_request_creates_the_task_map(
        self, monkeypatch, fake_ws
    ):
        monkeypatch.setattr(calibration, "_run_manual", AsyncMock())
        await calibration._handle_manual(fake_ws, valid_manual_msg)
        assert "gr4j" in fake_ws.state.manual_tasks
        await fake_ws.state.manual_tasks["gr4j"]

    async def test_supersedes_same_model_only(self, monkeypatch, fake_ws):
        monkeypatch.setattr(calibration, "_run_manual", AsyncMock())
        same = await parked_task()
        other = await parked_task()
        fake_ws.state.manual_tasks = {"gr4j": same, "bucket": other}
        await calibration._handle_manual(fake_ws, valid_manual_msg)
        assert same.cancelled() or same.cancelling()
        assert not other.cancelled()
        await fake_ws.state.manual_tasks["gr4j"]
        other.cancel()


class TestRunManual:
    async def test_simulates_and_replies(self, fake_ws, joined_data):
        await calibration._run_manual(
            fake_ws,
            "061004",
            "2016-01-01",
            "2016-12-31",
            "ministry_grid",
            3,
            "gr4j",
            None,
            "none",
            1,
            gr4j_defaults,
            7,
        )
        reply = fake_ws.sent[0]
        assert reply["type"] == "calibration_result"
        assert reply["data"]["hydroModel"] == "gr4j"
        assert reply["data"]["requestId"] == 7
        assert len(reply["data"]["simulation"]) == 366 + 365
        assert reply["data"]["objectives"]["rmse"] is not None

    async def test_failure_sends_calibration_error(self, fake_ws, joined_data):
        # a wrong parameter count makes the Rust model raise
        await calibration._run_manual(
            fake_ws,
            "061004",
            "2016-01-01",
            "2016-12-31",
            "ministry_grid",
            3,
            "gr4j",
            None,
            "none",
            1,
            [1.0],
            7,
        )
        reply = fake_ws.sent[0]
        assert reply["type"] == "calibration_error"
        assert reply["data"]["hydroModel"] == "gr4j"
        assert reply["data"]["requestId"] == 7


class TestHandleStart:
    @pytest.mark.parametrize(
        ["overrides", "match"],
        [
            ({"station": "999"}, "Unknown station"),
            ({"method": "bogus"}, "Unknown weather method"),
            ({"start": "x"}, "Invalid calibration date range"),
            ({"n_stations": "x"}, "Invalid number of nearest stations"),
            ({"hydroModels": "gr4j"}, "Unknown hydro model"),
            ({"hydroModels": []}, "Unknown hydro model"),
            ({"hydroModels": ["bogus"]}, "Unknown hydro model"),
            ({"snowModel": 3}, "Unknown snow model"),
            ({"objective": "bogus"}, "Unknown objective"),
            ({"transformation": "bogus"}, "Unknown transformation"),
            ({"algorithm": "bogus"}, "Unknown algorithm"),
            ({"runId": None}, "Invalid numeric calibration field"),
            ({"algorithmParams": "x"}, "Invalid algorithm parameters"),
            (
                {"algorithmParams": {"seed": "abc"}},
                "Invalid algorithm parameters",
            ),
        ],
    )
    async def test_validation_errors(self, fake_ws, overrides, match):
        await calibration._handle_start(
            fake_ws, {**valid_start_msg, **overrides}
        )
        assert fake_ws.sent[0]["type"] == "error"
        assert match in fake_ws.sent[0]["data"]

    async def test_installs_stops_and_tasks(self, monkeypatch, fake_ws):
        run = AsyncMock()
        monkeypatch.setattr(calibration, "_run_model_calibration", run)
        stale = threading.Event()
        fake_ws.state.calibration_stops = {"tank": stale}
        await calibration._handle_start(
            fake_ws, {**valid_start_msg, "hydroModels": ["gr4j", "bucket"]}
        )
        # the previous run is stopped, fresh events are installed per model
        assert stale.is_set()
        assert set(fake_ws.state.calibration_stops) == {"gr4j", "bucket"}
        assert not fake_ws.state.calibration_stops["gr4j"].is_set()
        await asyncio.gather(*fake_ws.state.tasks)
        assert run.await_count == 2


class TestHandleStop:
    async def test_without_stops(self, fake_ws):
        await calibration._handle_stop(fake_ws, {})

    async def test_stops_everything(self, fake_ws):
        stops = {"gr4j": threading.Event(), "bucket": threading.Event()}
        fake_ws.state.calibration_stops = stops
        await calibration._handle_stop(fake_ws, {})
        assert all(event.is_set() for event in stops.values())

    async def test_stops_one_model(self, fake_ws):
        stops = {"gr4j": threading.Event(), "bucket": threading.Event()}
        fake_ws.state.calibration_stops = stops
        await calibration._handle_stop(fake_ws, {"hydroModel": "gr4j"})
        assert stops["gr4j"].is_set()
        assert not stops["bucket"].is_set()

    async def test_unknown_model_is_ignored(self, fake_ws):
        stops = {"gr4j": threading.Event()}
        fake_ws.state.calibration_stops = stops
        await calibration._handle_stop(fake_ws, {"hydroModel": "tank"})
        assert not stops["gr4j"].is_set()


class TestRunModelCalibration:
    @staticmethod
    async def run(fake_ws, stop_event=None, params=None):
        await calibration._run_model_calibration(
            fake_ws,
            "061004",
            "2016-01-01",
            "2016-12-31",
            "ministry_grid",
            3,
            "gr4j",
            None,
            "rmse",
            "none",
            0,
            "sce",
            params or {},
            3,
            stop_event or threading.Event(),
        )

    @staticmethod
    def frame_args(step: int, done: bool):
        return (
            step,
            done,
            np.array(gr4j_defaults),
            np.full(366, 1.0),
            np.array([1.0, 0.5, 0.5]),
        )

    async def test_streams_frames_with_throttled_simulation(
        self, monkeypatch, fake_ws, joined_data
    ):
        def fake_stream(data, *args, callback, stop_event, **kwargs):
            callback(*self.frame_args(0, False))
            callback(*self.frame_args(1, False))
            callback(*self.frame_args(2, True))
            return np.array(gr4j_defaults), None

        monkeypatch.setattr(
            calibration.holmes.model, "calibrate_stream", fake_stream
        )
        await self.run(fake_ws)
        frames = [f["data"] for f in fake_ws.sent]
        assert [frame["step"] for frame in frames] == [0, 1, 2]
        # first frame carries the simulation, the immediate second is
        # throttled, the final done frame always carries it
        assert frames[0]["simulation"] is not None
        assert frames[1]["simulation"] is None
        assert frames[2]["simulation"] is not None
        assert frames[2]["done"] is True
        assert not frames[2]["stopped"]

    async def test_stop_synthesises_final_frame(
        self, monkeypatch, fake_ws, joined_data
    ):
        stop = threading.Event()

        def fake_stream(data, *args, callback, stop_event, **kwargs):
            callback(*self.frame_args(0, False))
            stop_event.set()
            return np.array(gr4j_defaults), None

        monkeypatch.setattr(
            calibration.holmes.model, "calibrate_stream", fake_stream
        )
        await self.run(fake_ws, stop_event=stop)
        final = fake_ws.sent[-1]["data"]
        assert final["stopped"] is True
        assert final["done"] is True
        assert final["step"] == 0

    async def test_stop_after_done_frame_adds_nothing(
        self, monkeypatch, fake_ws, joined_data
    ):
        stop = threading.Event()

        def fake_stream(data, *args, callback, stop_event, **kwargs):
            callback(*self.frame_args(0, True))
            stop_event.set()
            return np.array(gr4j_defaults), None

        monkeypatch.setattr(
            calibration.holmes.model, "calibrate_stream", fake_stream
        )
        await self.run(fake_ws, stop_event=stop)
        assert len(fake_ws.sent) == 1

    async def test_stop_before_any_frame_adds_nothing(
        self, monkeypatch, fake_ws, joined_data
    ):
        stop = threading.Event()

        def fake_stream(data, *args, callback, stop_event, **kwargs):
            stop_event.set()
            return np.array(gr4j_defaults), None

        monkeypatch.setattr(
            calibration.holmes.model, "calibrate_stream", fake_stream
        )
        await self.run(fake_ws, stop_event=stop)
        assert fake_ws.sent == []

    async def test_stream_failure_sends_calibration_error(
        self, monkeypatch, fake_ws, joined_data
    ):
        def fake_stream(data, *args, **kwargs):
            raise RuntimeError("sce blew up")

        monkeypatch.setattr(
            calibration.holmes.model, "calibrate_stream", fake_stream
        )
        await self.run(fake_ws)
        reply = fake_ws.sent[0]
        assert reply["type"] == "calibration_error"
        assert reply["data"]["runId"] == 3

    async def test_data_failure_sends_calibration_error(
        self, monkeypatch, fake_ws
    ):
        monkeypatch.setattr(
            calibration,
            "get_data",
            AsyncMock(side_effect=RuntimeError("no data")),
        )
        await self.run(fake_ws)
        assert fake_ws.sent[0]["type"] == "calibration_error"


class TestValidDates:
    @pytest.mark.parametrize(
        ["start", "end", "expected"],
        [
            ("2020-01-01", "2020-12-31", True),
            (None, "2020-12-31", False),
            ("abc", "2020-12-31", False),
            ("2020-01-01", 3, False),
        ],
    )
    def test_cases(self, start, end, expected):
        assert calibration._valid_dates(start, end) is expected


class TestParseSnow:
    @pytest.mark.parametrize(
        ["raw", "expected"],
        [
            ("none", (True, None)),
            ("cemaneige", (True, "cemaneige")),
            ("bogus", (False, None)),
            (None, (False, None)),
        ],
    )
    def test_cases(self, raw, expected):
        assert calibration._parse_snow(raw) == expected


class TestCoerceInt:
    @pytest.mark.parametrize(
        ["value", "expected"],
        [(3, 3), ("4", 4), (2.9, 2), (None, None), ("x", None)],
    )
    def test_cases(self, value, expected):
        assert calibration._coerce_int(value) == expected


class TestCoerceNStations:
    @pytest.mark.parametrize(
        ["value", "expected"],
        [(1, 1), (5, 5), ("2", 2), (0, None), (6, None), (None, None)],
    )
    def test_cases(self, value, expected):
        assert calibration._coerce_n_stations(value) == expected


class TestCoerceFloats:
    @pytest.mark.parametrize(
        ["values", "expected"],
        [
            ([1, "2.5"], [1.0, 2.5]),
            ("x", None),
            (["a"], None),
            ([None], None),
        ],
    )
    def test_cases(self, values, expected):
        assert calibration._coerce_floats(values) == expected


class TestCoerceAlgorithmParams:
    def test_none_gives_defaults(self):
        params = calibration._coerce_algorithm_params(None)
        assert params is not None
        assert params["n_complexes"] == 25
        assert isinstance(params["n_complexes"], int)
        assert isinstance(params["p_convergence_threshold"], float)

    def test_overrides_are_coerced(self):
        params = calibration._coerce_algorithm_params(
            {"seed": "7", "p_convergence_threshold": "0.2"}
        )
        assert params is not None
        assert params["seed"] == 7
        assert params["p_convergence_threshold"] == 0.2

    def test_non_dict_is_invalid(self):
        assert calibration._coerce_algorithm_params("x") is None

    def test_bad_value_is_invalid(self):
        assert calibration._coerce_algorithm_params({"seed": "abc"}) is None
