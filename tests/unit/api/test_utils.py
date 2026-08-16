import json
from datetime import date, datetime
from unittest.mock import AsyncMock

import polars as pl
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.websockets import WebSocketState

from holmes.api.utils import (
    JSONResponse,
    convert_for_json,
    get_headers,
    get_json_params,
    get_path_params,
    get_query_string_params,
    send,
    with_headers,
    with_json_params,
    with_path_params,
    with_query_string_params,
)


def make_request(
    body: bytes = b"",
    query_string: bytes = b"",
    path_params: dict | None = None,
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/",
        "query_string": query_string,
        "headers": headers or [],
        "path_params": path_params or {},
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


class TestGetJsonParams:
    async def test_returns_args_and_present_opt_args(self):
        req = make_request(body=json.dumps({"a": 1, "b": 2}).encode())
        params = await get_json_params(req, args=["a"], opt_args=["b", "c"])
        assert params == {"a": 1, "b": 2}

    async def test_no_args(self):
        req = make_request(body=b"{}")
        assert await get_json_params(req) == {}

    async def test_invalid_json_returns_400(self):
        req = make_request(body=b"not json")
        resp = await get_json_params(req, args=["a"])
        assert isinstance(resp, Response)
        assert resp.status_code == 400

    async def test_missing_arg_returns_400(self):
        req = make_request(body=b"{}")
        resp = await get_json_params(req, args=["a"])
        assert isinstance(resp, Response)
        assert resp.status_code == 400


class TestGetQueryStringParams:
    async def test_returns_params(self):
        req = make_request(query_string=b"a=1&b=2")
        params = await get_query_string_params(
            req, args=["a"], opt_args=["b", "c"]
        )
        assert params == {"a": "1", "b": "2"}

    async def test_no_args(self):
        req = make_request()
        assert await get_query_string_params(req) == {}

    async def test_missing_arg_returns_400(self):
        req = make_request(query_string=b"b=2")
        resp = await get_query_string_params(req, args=["a"])
        assert isinstance(resp, Response)
        assert resp.status_code == 400


class TestGetPathParams:
    async def test_returns_params(self):
        req = make_request(path_params={"a": 1, "b": 2})
        params = await get_path_params(req, args=["a"], opt_args=["b", "c"])
        assert params == {"a": 1, "b": 2}

    async def test_no_args(self):
        req = make_request()
        assert await get_path_params(req) == {}

    async def test_missing_arg_returns_400(self):
        req = make_request(path_params={})
        resp = await get_path_params(req, args=["a"])
        assert isinstance(resp, Response)
        assert resp.status_code == 400


class TestGetHeaders:
    async def test_returns_headers(self):
        req = make_request(headers=[(b"x-a", b"1"), (b"x-b", b"2")])
        params = await get_headers(req, args=["x-a"], opt_args=["x-b", "x-c"])
        assert params == {"x-a": "1", "x-b": "2"}

    async def test_no_args(self):
        req = make_request()
        assert await get_headers(req) == {}

    async def test_missing_header_returns_400(self):
        req = make_request(headers=[])
        resp = await get_headers(req, args=["x-a"])
        assert isinstance(resp, Response)
        assert resp.status_code == 400


class TestWithJsonParams:
    async def test_passes_params_with_dash_conversion(self):
        @with_json_params(args=["some-arg"], opt_args="other")
        async def handler(req, some_arg, other="x"):
            return PlainTextResponse(f"{some_arg}-{other}")

        req = make_request(body=json.dumps({"some-arg": "a"}).encode())
        resp = await handler(req)
        assert resp.body == b"a-x"

    async def test_single_string_arg(self):
        @with_json_params(args="a")
        async def handler(req, a):
            return PlainTextResponse(a)

        req = make_request(body=json.dumps({"a": "val"}).encode())
        resp = await handler(req)
        assert resp.body == b"val"

    async def test_propagates_400(self):
        @with_json_params(args=["a"])
        async def handler(req, a):  # pragma: no cover
            return PlainTextResponse(a)

        resp = await handler(make_request(body=b"{}"))
        assert resp.status_code == 400


class TestWithQueryStringParams:
    async def test_passes_params(self):
        @with_query_string_params(args="some-arg", opt_args=["b"])
        async def handler(req, some_arg, b="x"):
            return PlainTextResponse(f"{some_arg}-{b}")

        resp = await handler(make_request(query_string=b"some-arg=a&b=2"))
        assert resp.body == b"a-2"

    async def test_propagates_400(self):
        @with_query_string_params(args=["a"])
        async def handler(req, a):  # pragma: no cover
            return PlainTextResponse(a)

        resp = await handler(make_request())
        assert resp.status_code == 400


class TestWithPathParams:
    async def test_passes_params(self):
        @with_path_params(args="some-arg", opt_args=["b"])
        async def handler(req, some_arg, b="x"):
            return PlainTextResponse(f"{some_arg}-{b}")

        resp = await handler(
            make_request(path_params={"some-arg": "a", "b": "2"})
        )
        assert resp.body == b"a-2"

    async def test_propagates_400(self):
        @with_path_params(args=["a"])
        async def handler(req, a):  # pragma: no cover
            return PlainTextResponse(a)

        resp = await handler(make_request())
        assert resp.status_code == 400


class TestWithHeaders:
    async def test_passes_params(self):
        @with_headers(args="x-a", opt_args=["x-b"])
        async def handler(req, x_a, x_b="x"):
            return PlainTextResponse(f"{x_a}-{x_b}")

        resp = await handler(make_request(headers=[(b"x-a", b"1")]))
        assert resp.body == b"1-x"

    async def test_propagates_400(self):
        @with_headers(args=["x-a"])
        async def handler(req, x_a):  # pragma: no cover
            return PlainTextResponse(x_a)

        resp = await handler(make_request())
        assert resp.status_code == 400


class TestJsonResponse:
    def test_converts_payload(self):
        resp = JSONResponse({"when": date(2020, 1, 1)})
        assert json.loads(bytes(resp.body)) == {"when": 1577836800}


class TestConvertForJson:
    def test_recurses_containers(self):
        data = {"a": [1, (2, 3)], "b": {"c": "x"}}
        assert convert_for_json(data) == {"a": [1, [2, 3]], "b": {"c": "x"}}

    def test_datetime_to_timestamp(self):
        moment = datetime(2020, 1, 1, 12, 0, 0)
        assert convert_for_json(moment) == 1577880000

    def test_datetime_as_str(self):
        moment = datetime(2020, 1, 1, 12, 0, 0)
        assert (
            convert_for_json(moment, dates_as_str=True)
            == "2020-01-01 12:00:00+00:00"
        )

    def test_date_to_timestamp(self):
        assert convert_for_json(date(2020, 1, 1)) == 1577836800

    def test_date_as_str(self):
        assert convert_for_json(date(2020, 1, 1), dates_as_str=True) == (
            "2020-01-01"
        )

    def test_dataframe_nan_and_inf_become_null(self):
        data = pl.DataFrame(
            {
                "x": [1.0, float("nan"), float("inf"), -float("inf")],
                "when": [date(2020, 1, 1)] * 4,
            }
        )
        converted = convert_for_json(data)
        assert [row["x"] for row in converted] == [1.0, None, None, None]
        assert converted[0]["when"] == 1577836800

    def test_scalar_passthrough(self):
        assert convert_for_json("x") == "x"
        assert convert_for_json(3) == 3
        assert convert_for_json(None) is None


class TestSend:
    async def test_sends_converted_payload(self, fake_ws):
        assert await send(fake_ws, "event", {"when": date(2020, 1, 1)})
        assert fake_ws.sent == [
            {"type": "event", "data": {"when": 1577836800}}
        ]

    async def test_disconnected_returns_false(self, fake_ws):
        fake_ws.client_state = WebSocketState.DISCONNECTED
        assert not await send(fake_ws, "event", {})
        assert fake_ws.sent == []

    async def test_runtime_error_returns_false(self, fake_ws):
        fake_ws.send_json = AsyncMock(side_effect=RuntimeError("closed"))
        assert not await send(fake_ws, "event", {})
