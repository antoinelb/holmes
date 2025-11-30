import polars as pl
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Route, WebSocketRoute
from starlette.websockets import WebSocket, WebSocketDisconnect

from holmes import data, hydro
from holmes.utils import plotting

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
        WebSocketRoute(
            "/run_automatic",
            endpoint=_run_automatic,
        ),
    ]


async def precompile_functions() -> None:
    await hydro.precompile()


###########
# private #
###########


async def _get_available_config(_: Request) -> Response:
    catchments = data.get_available_catchments()
    config = {
        "hydrological_model": hydro.hydrological_models,
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
        "theme",
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
    theme: str,
) -> Response:
    data_ = hydro.read_transformed_hydro_data(
        catchment, calibration_start, calibration_end, snow_model
    )
    simulation = hydro.run_model(data_, hydrological_model, params)
    objective = hydro.evaluate_simulation(
        data_["flow"].to_numpy().squeeze(),
        simulation,
        objective_criteria.lower(),  # type: ignore
        streamflow_transformation.split(":")[1].strip().lower(),  # type: ignore
    )
    optimal = hydro.get_optimal_for_criteria(
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

    fig = hydro.calibration.plot_calibration(
        data_.with_columns(pl.Series("simulation", simulation)),
        results,
        objective_criteria.lower(),
        optimal,
        template=plotting.light_template if theme == "light" else None,
    )

    return JSONResponse(
        {
            "fig": fig.to_json(),
            "results": results,
        }
    )


async def _run_automatic(websocket: WebSocket) -> None:
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
        theme = config["theme"]

        data_ = hydro.read_transformed_hydro_data(
            catchment, calibration_start, calibration_end, snow_model
        )

        optimal = hydro.get_optimal_for_criteria(
            objective_criteria.lower(),  # type: ignore
        )

        async def send_progress(update: dict):
            current_results = {
                "params": update.pop("params_history"),
                "objective": update.pop("objective_history"),
            }

            params = {
                param: values[-1]
                for param, values in current_results["params"].items()
            }
            simulation = hydro.run_model(data_, hydrological_model, params)

            fig = hydro.calibration.plot_calibration(
                data_.with_columns(pl.Series("simulation", simulation)),
                current_results,
                objective_criteria.lower(),
                optimal,
                template=plotting.light_template if theme == "light" else None,
            )

            await websocket.send_json(
                {
                    **update,
                    "fig": fig.to_json(),
                    "results": current_results,
                }
            )

        results = await hydro.calibration.calibrate_model(
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

        params = {
            param: values[-1] for param, values in results["params"].items()
        }
        simulation = hydro.run_model(data_, hydrological_model, params)
        optimal = hydro.get_optimal_for_criteria(
            objective_criteria.lower(),  # type: ignore
        )
        fig = hydro.calibration.plot_calibration(
            data_.with_columns(pl.Series("simulation", simulation)),
            results,
            objective_criteria.lower(),
            optimal,
            template=plotting.light_template if theme == "light" else None,
        )

        await websocket.send_json(
            {
                "type": "complete",
                "fig": fig.to_json(),
                "results": results,
            }
        )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        raise e
        # try:
        #     await websocket.send_json({"type": "error", "message": str(e)})
        # except Exception:
        #     pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
