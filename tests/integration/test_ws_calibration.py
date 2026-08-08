import holmes_rs

from tests.integration.conftest import recv_until

gr4j_defaults = list(holmes_rs.hydro.gr4j.init()[0])

base_request = {
    "station": "061004",
    "method": "ministry_grid",
    "start": "2016-01-01",
    "end": "2016-12-31",
    "n_stations": 3,
    "warmupYears": 1,
}

# converges within a handful of steps on one year of synthetic data
fast_sce = {
    "seed": 0,
    "n_complexes": 2,
    "k_stop": 1,
    "p_convergence_threshold": 0.5,
    "geometric_range_threshold": 0.5,
    "max_evaluations": 60,
}

# never converges on its own; every run using it is explicitly stopped
endless_sce = {
    "seed": 0,
    "n_complexes": 2,
    "k_stop": 10000,
    "p_convergence_threshold": 0.0,
    "geometric_range_threshold": 0.0,
    "max_evaluations": 50000,
}


def start_message(**overrides) -> dict:
    msg = {
        "type": "calibration_start",
        **base_request,
        "hydroModels": ["gr4j"],
        "snowModel": "none",
        "objective": "rmse",
        "transformation": "none",
        "algorithm": "sce",
        "runId": 1,
        "algorithmParams": fast_sce,
    }
    msg.update(overrides)
    return msg


class TestInfo:
    def test_serves_bounds(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "calibration_info"})
            msg = recv_until(ws, "calibration_info")
            assert "gr4j" in msg["data"]["hydro"]


class TestData:
    def test_echoes_request_with_qnbv(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "calibration_data", **base_request})
            msg = recv_until(ws, "calibration_data")
            assert msg["data"]["station"] == "061004"
            assert msg["data"]["warmupYears"] == 1
            assert msg["data"]["qnbv"] > 0
            assert len(msg["data"]["data"]) == 366 + 365


class TestManual:
    def test_without_snow(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "type": "calibration_manual",
                    **base_request,
                    "hydroModel": "gr4j",
                    "snowModel": "none",
                    "transformation": "none",
                    "requestId": 7,
                    "hydroParams": gr4j_defaults,
                }
            )
            msg = recv_until(ws, "calibration_result")
            assert msg["data"]["hydroModel"] == "gr4j"
            assert msg["data"]["requestId"] == 7
            assert msg["data"]["objectives"]["rmse"] is not None

    def test_with_snow(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                {
                    "type": "calibration_manual",
                    **base_request,
                    "hydroModel": "gr4j",
                    "snowModel": "cemaneige",
                    "transformation": "none",
                    "requestId": 8,
                    "hydroParams": gr4j_defaults,
                }
            )
            msg = recv_until(ws, "calibration_result")
            assert msg["data"]["requestId"] == 8


class TestStart:
    def test_runs_to_convergence(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(start_message())
            steps = []
            while True:
                msg = recv_until(ws, "calibration_step")
                steps.append(msg["data"])
                if msg["data"]["done"]:
                    break
            assert [s["step"] for s in steps] == list(range(len(steps)))
            assert all(s["hydroModel"] == "gr4j" for s in steps)
            assert all(s["runId"] == 1 for s in steps)
            assert not steps[-1]["stopped"]
            # the first frame always carries the simulation
            assert steps[0]["simulation"] is not None
            assert steps[-1]["params"] is not None

    def test_stop_synthesises_final_frame(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(start_message(algorithmParams=endless_sce, runId=2))
            recv_until(ws, "calibration_step")
            recv_until(ws, "calibration_step")
            ws.send_json({"type": "calibration_stop"})
            while True:
                msg = recv_until(ws, "calibration_step")
                if msg["data"]["done"]:
                    break
            assert msg["data"]["stopped"] is True
            assert msg["data"]["runId"] == 2

    def test_targeted_stop_leaves_other_models_running(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(
                start_message(
                    algorithmParams=endless_sce,
                    hydroModels=["gr4j", "bucket"],
                    runId=3,
                )
            )
            ws.send_json({"type": "calibration_stop", "hydroModel": "gr4j"})
            gr4j_done = False
            bucket_after_gr4j = False
            while not (gr4j_done and bucket_after_gr4j):
                msg = recv_until(ws, "calibration_step")
                if msg["data"]["hydroModel"] == "gr4j":
                    if msg["data"]["done"]:
                        assert msg["data"]["stopped"] is True
                        gr4j_done = True
                elif gr4j_done:
                    # bucket still streams after gr4j finished
                    bucket_after_gr4j = True
            ws.send_json({"type": "calibration_stop"})
            while True:
                msg = recv_until(ws, "calibration_step")
                if (
                    msg["data"]["hydroModel"] == "bucket"
                    and msg["data"]["done"]
                ):
                    break

    def test_disconnect_during_calibration_cleans_up(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.send_json(start_message(algorithmParams=endless_sce, runId=4))
            recv_until(ws, "calibration_step")
        # leaving the context closes the socket; the cleanup's stop events
        # end the SCE thread, so exiting does not hang and a new connection
        # works immediately
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "model_info"})
            assert recv_until(ws, "model_info")
