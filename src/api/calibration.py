from datetime import datetime, timedelta

import polars as pl
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from src import data, hydro

from .utils import JSONResponse, with_json_params

##########
# public #
##########


def get_routes() -> list[BaseRoute]:
    return [
        Route(
            "/config",
            endpoint=_get_available_config,
            methods=["GET"],
        ),
        Route(
            "/run_manual",
            endpoint=_run_manual,
            methods=["POST"],
        ),
        Route(
            "/run_automatic",
            endpoint=_run_automatic,
            methods=["POST"],
        ),
        WebSocketRoute(
            "/run_automatic_ws",
            endpoint=_run_automatic_ws,
        ),
    ]


async def precompile_functions() -> None:
    await hydro.models.precompile()


###########
# private #
###########


async def _get_available_config(_: Request) -> Response:
    catchments = data.get_available_catchments()
    config = {
        "hydrological_model": hydro.models.hydrological_models,
        "catchment": catchments,
        "snow_model": {"none": {}, **hydro.snow.snow_models},
        "objective_criteria": ["RMSE", "NSE", "KGE"],
        "streamflow_transformation": [
            "Low Flows: log",
            "Medium Flows: sqrt",
            "High Flows: none",
        ],
        "algorithm": ["Manual", "Automatic - SCE"],
    }
    return JSONResponse(config)


@with_json_params(
    args=[
        "hydrological_model",
        "catchment",
        "snow_model",
        "objective_criteria",
        "streamflow_transformation",
        "calibration_start",
        "calibration_end",
        "params",
        "prev_results",
    ]
)
async def _run_manual(
    _: Request,
    hydrological_model: str,
    catchment: str,
    snow_model: str,
    objective_criteria: str,
    streamflow_transformation: str,
    calibration_start: str,
    calibration_end: str,
    params: dict[str, float | int],
    prev_results: dict[str, dict[str, list[int | float]]] | None,
) -> Response:
    data_ = _read_data(
        catchment, calibration_start, calibration_end, snow_model
    )
    simulation = hydro.models.run_model(data_, hydrological_model, params)
    objective = hydro.utils.evaluate_simulation(
        simulation["flow"].to_numpy().squeeze(),
        simulation["simulation"].to_numpy().squeeze(),
        objective_criteria.lower(),  # type: ignore
        streamflow_transformation.split(":")[1].strip().lower(),  # type: ignore
    )
    optimal = hydro.utils.get_optimal_for_criteria(
        objective_criteria.lower(),  # type: ignore
    )

    results = {
        "params": {
            param: (
                [*prev_results["params"][param], val]
                if prev_results is not None
                else [val]
            )
            for param, val in params.items()
        },
        "objective": (
            [*prev_results["objective"], objective]
            if prev_results is not None
            else [objective]
        ),
    }

    fig = hydro.models.plot_simulation(
        simulation, results, objective_criteria.lower(), optimal
    )

    return JSONResponse(
        {
            "fig": fig.to_json(),
            "results": results,
        }
    )


@with_json_params(
    args=[
        "hydrological_model",
        "catchment",
        "snow_model",
        "objective_criteria",
        "streamflow_transformation",
        "calibration_start",
        "calibration_end",
        "ngs",
        "npg",
        "mings",
        "nspl",
        "maxn",
        "kstop",
        "pcento",
        "peps",
    ]
)
async def _run_automatic(
    _: Request,
    hydrological_model: str,
    catchment: str,
    snow_model: str,
    objective_criteria: str,
    streamflow_transformation: str,
    calibration_start: str,
    calibration_end: str,
    ngs: str,
    npg: str,
    mings: str,
    nspl: str,
    maxn: str,
    kstop: str,
    pcento: str,
    peps: str,
) -> Response:
    data_ = _read_data(
        catchment, calibration_start, calibration_end, snow_model
    )
    results = await hydro.models.calibrate_model(
        data_,
        hydrological_model,
        objective_criteria.lower(),  # type: ignore
        streamflow_transformation.split(":")[1].strip().lower(),  # type: ignore
        int(ngs),
        int(npg),
        int(mings),
        int(nspl),
        int(maxn),
        int(kstop),
        float(pcento),
        float(peps),
    )

    # Generate final plot
    params = {
        param: values[-1] for param, values in results["params"].items()
    }
    simulation = hydro.models.run_model(data_, hydrological_model, params)
    optimal = hydro.utils.get_optimal_for_criteria(
        objective_criteria.lower(),  # type: ignore
    )
    fig = hydro.models.plot_simulation(
        simulation, results, objective_criteria.lower(), optimal
    )

    return JSONResponse(
        {
            "fig": fig.to_json(),
            "results": results,
        }
    )


async def _run_automatic_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for automatic calibration with real-time progress.

    Protocol:
    1. Accept connection
    2. Receive calibration config (JSON)
    3. Run SCE with progress callback
    4. Stream progress updates
    5. Send final results
    6. Close connection
    """
    await websocket.accept()

    try:
        # Receive configuration
        config = await websocket.receive_json()

        # Extract parameters
        hydrological_model = config["hydrological_model"]
        catchment = config["catchment"]
        snow_model = config["snow_model"]
        objective_criteria = config["objective_criteria"]
        streamflow_transformation = config["streamflow_transformation"]
        calibration_start = config["calibration_start"]
        calibration_end = config["calibration_end"]
        ngs = int(config["ngs"])
        npg = int(config["npg"])
        mings = int(config["mings"])
        nspl = int(config["nspl"])
        maxn = int(config["maxn"])
        kstop = int(config["kstop"])
        pcento = float(config["pcento"])
        peps = float(config["peps"])

        # Read data
        data_ = _read_data(
            catchment, calibration_start, calibration_end, snow_model
        )

        # Get optimal value for plotting
        optimal = hydro.utils.get_optimal_for_criteria(
            objective_criteria.lower(),  # type: ignore
        )

        # Define progress callback that generates and sends plots
        async def send_progress(update: dict):
            # Extract current results from progress update
            current_results = {
                "params": update.pop("params_history"),
                "objective": update.pop("objective_history"),
            }

            # Generate current best simulation
            params = {
                param: values[-1]
                for param, values in current_results["params"].items()
            }
            simulation = hydro.models.run_model(data_, hydrological_model, params)

            # Generate plot
            fig = hydro.models.plot_simulation(
                simulation,
                current_results,
                objective_criteria.lower(),
                optimal
            )

            # Send progress with plot
            await websocket.send_json({
                **update,
                "fig": fig.to_json(),
                "results": current_results,
            })

        # Run calibration
        results = await hydro.models.calibrate_model(
            data_,
            hydrological_model,
            objective_criteria.lower(),  # type: ignore
            streamflow_transformation.split(":")[1].strip().lower(),  # type: ignore
            ngs,
            npg,
            mings,
            nspl,
            maxn,
            kstop,
            pcento,
            peps,
            send_progress,
        )

        # Generate final plot
        params = {
            param: values[-1] for param, values in results["params"].items()
        }
        simulation = hydro.models.run_model(data_, hydrological_model, params)
        optimal = hydro.utils.get_optimal_for_criteria(
            objective_criteria.lower(),  # type: ignore
        )
        fig = hydro.models.plot_simulation(
            simulation, results, objective_criteria.lower(), optimal
        )

        # Send final results
        await websocket.send_json(
            {
                "type": "complete",
                "fig": fig.to_json(),
                "results": results,
            }
        )

    except WebSocketDisconnect:
        # Client disconnected - could add cancellation logic here
        pass
    except Exception as e:
        # Send error to client
        try:
            await websocket.send_json(
                {"type": "error", "message": str(e)}
            )
        except:
            pass
    finally:
        try:
            await websocket.close()
        except:
            pass


def _read_data(
    catchment: str, start: str, end: str, snow_model: str
) -> pl.DataFrame:
    warmup_length = 365 * 3  # 3 years of warmup

    data_ = data.read_catchment_data(catchment).rename(
        {
            "Date": "date",
            "P": "precipitation",
            "E0": "evapotranspiration",
            "Qo": "flow",
            "T": "temperature",
        }
    )

    # keep only wanted data plus a warmup period
    data_ = data_.filter(
        pl.col("date").is_between(
            datetime.strptime(start, "%Y-%m-%d")
            - timedelta(days=warmup_length),
            datetime.strptime(end, "%Y-%m-%d"),
        )
    )

    # handle snow
    if snow_model == "none":
        pass
    else:
        raise NotImplementedError()

    return data_.collect()
