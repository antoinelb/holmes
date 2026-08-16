import json
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable

import polars as pl
from starlette.requests import Request
from starlette.responses import JSONResponse as _JSONResponse
from starlette.responses import PlainTextResponse, Response
from starlette.websockets import WebSocket, WebSocketState

from holmes.utils.print import warn_print

#########
# types #
#########


NumericType = [
    pl.Decimal,
    pl.Float32,
    pl.Float64,
    pl.Int8,
    pl.Int16,
    pl.Int32,
    pl.Int64,
    pl.Int128,
    pl.UInt8,
    pl.UInt16,
    pl.UInt32,
    pl.UInt64,
]

##########
# public #
##########


async def get_json_params(
    req: Request,
    args: list[str] | None = None,
    opt_args: list[str] | None = None,
) -> dict[str, Any] | Response:
    if args is None:
        args = []
    if opt_args is None:
        opt_args = []
    try:
        data = json.loads(await req.body())
    except ValueError:
        return PlainTextResponse("Wrong data type was sent.", status_code=400)
    try:
        args_ = {arg: data[arg] for arg in args}
        opt_args_ = {arg: data[arg] for arg in opt_args if arg in data}
    except KeyError:
        return PlainTextResponse(
            "There are missing parameters.", status_code=400
        )
    return {**args_, **opt_args_}


async def get_query_string_params(
    req: Request,
    args: list[str] | None = None,
    opt_args: list[str] | None = None,
) -> dict[str, Any] | Response:
    if args is None:
        args = []
    if opt_args is None:
        opt_args = []
    try:
        args_ = {arg: req.query_params[arg] for arg in args}
        opt_args_ = {
            arg: req.query_params[arg]
            for arg in opt_args
            if arg in req.query_params
        }
    except KeyError:
        return PlainTextResponse(
            "There are missing parameters.", status_code=400
        )
    return {**args_, **opt_args_}


async def get_path_params(
    req: Request,
    args: list[str] | None = None,
    opt_args: list[str] | None = None,
) -> dict[str, Any] | Response:
    if args is None:
        args = []
    if opt_args is None:
        opt_args = []
    try:
        args_ = {arg: req.path_params[arg] for arg in args}
        opt_args_ = {
            arg: req.path_params[arg]
            for arg in opt_args
            if arg in req.path_params
        }
    except KeyError:
        return PlainTextResponse(
            "There are missing parameters.", status_code=400
        )
    return {**args_, **opt_args_}


async def get_headers(
    req: Request,
    args: list[str] | None = None,
    opt_args: list[str] | None = None,
) -> dict[str, Any] | Response:
    if args is None:
        args = []
    if opt_args is None:
        opt_args = []
    try:
        args_ = {arg: req.headers[arg] for arg in args}
        opt_args_ = {
            arg: req.headers[arg] for arg in opt_args if arg in req.headers
        }
    except KeyError:
        return PlainTextResponse("There are missing headers.", status_code=400)
    return {**args_, **opt_args_}


def with_json_params(
    args: list[str] | str | None = None,
    opt_args: list[str] | str | None = None,
) -> Callable[[Callable], Callable]:
    def decorator(
        fct: Callable[..., Awaitable[Response]],
    ) -> Callable[..., Awaitable[Response]]:
        async def wrapper(
            req: Request, *args_: Any, **kwargs_: Any
        ) -> Response:
            params = await get_json_params(
                req,
                args=[args] if isinstance(args, str) else args,
                opt_args=[opt_args] if isinstance(opt_args, str) else opt_args,
            )
            if isinstance(params, Response):
                return params
            params = {
                arg.replace("-", "_"): val for arg, val in params.items()
            }
            return await fct(req, *args_, **kwargs_, **params)

        return wrapper

    return decorator


def with_query_string_params(
    args: list[str] | str | None = None,
    opt_args: list[str] | str | None = None,
) -> Callable[[Callable], Callable]:
    def decorator(
        fct: Callable[..., Awaitable[Response]],
    ) -> Callable[..., Awaitable[Response]]:
        async def wrapper(
            req: Request, *args_: Any, **kwargs_: Any
        ) -> Response:
            params = await get_query_string_params(
                req,
                args=[args] if isinstance(args, str) else args,
                opt_args=[opt_args] if isinstance(opt_args, str) else opt_args,
            )
            if isinstance(params, Response):
                return params
            params = {
                arg.replace("-", "_"): val for arg, val in params.items()
            }
            return await fct(req, *args_, **kwargs_, **params)

        return wrapper

    return decorator


def with_path_params(
    args: list[str] | str | None = None,
    opt_args: list[str] | str | None = None,
) -> Callable[[Callable], Callable]:
    def decorator(
        fct: Callable[..., Awaitable[Response]],
    ) -> Callable[..., Awaitable[Response]]:
        async def wrapper(
            req: Request, *args_: Any, **kwargs_: Any
        ) -> Response:
            params = await get_path_params(
                req,
                args=[args] if isinstance(args, str) else args,
                opt_args=[opt_args] if isinstance(opt_args, str) else opt_args,
            )
            if isinstance(params, Response):
                return params
            params = {
                arg.replace("-", "_"): val for arg, val in params.items()
            }
            return await fct(req, *args_, **kwargs_, **params)

        return wrapper

    return decorator


def with_headers(
    args: list[str] | str | None = None,
    opt_args: list[str] | str | None = None,
) -> Callable[[Callable], Callable]:
    def decorator(
        fct: Callable[..., Awaitable[Response]],
    ) -> Callable[..., Awaitable[Response]]:
        async def wrapper(
            req: Request, *args_: Any, **kwargs_: Any
        ) -> Response:
            params = await get_headers(
                req,
                args=[args] if isinstance(args, str) else args,
                opt_args=[opt_args] if isinstance(opt_args, str) else opt_args,
            )
            if isinstance(params, Response):
                return params
            params = {
                arg.replace("-", "_"): val for arg, val in params.items()
            }
            return await fct(req, *args_, **kwargs_, **params)

        return wrapper

    return decorator


def JSONResponse(data: Any, *args: Any, **kwargs: Any) -> _JSONResponse:
    return _JSONResponse(convert_for_json(data), *args, **kwargs)


def convert_for_json(data: Any, *, dates_as_str: bool = False) -> Any:
    if isinstance(data, dict):
        return {
            key: convert_for_json(val, dates_as_str=dates_as_str)
            for key, val in data.items()
        }
    elif isinstance(data, (list, tuple)):
        return [
            convert_for_json(val, dates_as_str=dates_as_str) for val in data
        ]
    elif isinstance(data, datetime):
        if dates_as_str:
            return data.replace(tzinfo=timezone.utc).isoformat(" ")
        else:
            return int(data.replace(tzinfo=timezone.utc).timestamp())
    elif isinstance(data, date):
        if dates_as_str:
            return data.isoformat()
        else:
            return int(
                datetime.combine(data, datetime.min.time())
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
    elif isinstance(data, pl.DataFrame):
        return [
            convert_for_json(d, dates_as_str=dates_as_str)
            for d in data.with_columns(
                # NaN and ±inf are both invalid JSON: json.dumps emits bare
                # NaN/Infinity literals, which strict JSON.parse rejects,
                # discarding the whole message client-side
                pl.when(
                    pl.col(NumericType).is_infinite()
                    | pl.col(NumericType).is_nan()
                )
                .then(None)
                .otherwise(pl.col(NumericType))
                .name.keep(),
                # pl.col(pl.Date).dt.strftime("%Y-%m-%d"),
                # pl.col(pl.Datetime).dt.strftime("%Y-%m-%d %H:%M:%S"),
            ).to_dicts()
        ]
    else:
        return data


async def send(ws: WebSocket, event: str, data: Any) -> bool:
    if ws.client_state != WebSocketState.CONNECTED:
        warn_print(f"Cannot send '{event}': WebSocket not connected")
        return False

    try:
        await ws.send_json({"type": event, "data": convert_for_json(data)})
        return True
    except RuntimeError as exc:
        warn_print(f"Failed to send '{event}': {exc}")
        return False
    except Exception as exc:  # pragma: no cover
        warn_print(f"Unexpected error sending '{event}': {exc}")
        return False
