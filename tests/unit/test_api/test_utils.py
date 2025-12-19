"""Tests for src/api/utils.py - API decorators and helpers."""

import json
from datetime import date, datetime, timezone

import numpy as np
import polars as pl
import pytest
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

from holmes.api import utils

# Test get_json_params


@pytest.mark.asyncio
async def test_get_json_params_extracts_required_params():
    """Should extract required parameters."""

    async def receive():
        return {
            "body": json.dumps({"foo": "bar", "baz": 123}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    result = await utils.get_json_params(request, args=["foo", "baz"])

    assert isinstance(result, dict)
    assert result["foo"] == "bar"
    assert result["baz"] == 123


@pytest.mark.asyncio
async def test_get_json_params_missing_required_returns_error():
    """Should return error response for missing params."""

    async def receive():
        return {
            "body": json.dumps({"foo": "bar"}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    result = await utils.get_json_params(request, args=["foo", "missing"])

    assert isinstance(result, PlainTextResponse)
    assert result.status_code == 400


@pytest.mark.asyncio
async def test_get_json_params_optional_params():
    """Should handle optional parameters."""

    async def receive():
        return {
            "body": json.dumps({"foo": "bar"}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    result = await utils.get_json_params(
        request, args=["foo"], opt_args=["optional"]
    )

    assert isinstance(result, dict)
    assert result["foo"] == "bar"
    assert "optional" not in result


@pytest.mark.asyncio
async def test_get_json_params_optional_params_present():
    """Should include optional parameters when present."""

    async def receive():
        return {
            "body": json.dumps({"foo": "bar", "optional": "value"}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    result = await utils.get_json_params(
        request, args=["foo"], opt_args=["optional"]
    )

    assert isinstance(result, dict)
    assert result["foo"] == "bar"
    assert result["optional"] == "value"


@pytest.mark.asyncio
async def test_get_json_params_invalid_json_returns_error():
    """Should return error for invalid JSON."""

    async def receive():
        return {"body": b"not json", "type": "http.request"}

    request = Request({"type": "http", "method": "POST"}, receive)
    result = await utils.get_json_params(request)

    assert isinstance(result, PlainTextResponse)
    assert result.status_code == 400


@pytest.mark.asyncio
async def test_get_json_params_no_args():
    """Should work with no required args."""

    async def receive():
        return {
            "body": json.dumps({"foo": "bar"}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    result = await utils.get_json_params(request)

    assert isinstance(result, dict)
    assert result == {}


# Test get_query_string_params


@pytest.mark.asyncio
async def test_get_query_string_params_extracts_params():
    """Should extract query string parameters."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "query_string": b"foo=bar&baz=123",
        },
        receive,
    )
    result = await utils.get_query_string_params(request, args=["foo", "baz"])

    assert isinstance(result, dict)
    assert result["foo"] == "bar"
    assert result["baz"] == "123"  # Query params are always strings


@pytest.mark.asyncio
async def test_get_query_string_params_missing_returns_error():
    """Should return error for missing query params."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "query_string": b"foo=bar"}, receive
    )
    result = await utils.get_query_string_params(
        request, args=["foo", "missing"]
    )

    assert isinstance(result, PlainTextResponse)
    assert result.status_code == 400


@pytest.mark.asyncio
async def test_get_query_string_params_optional():
    """Should handle optional query parameters."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "query_string": b"foo=bar"}, receive
    )
    result = await utils.get_query_string_params(
        request, args=["foo"], opt_args=["optional"]
    )

    assert isinstance(result, dict)
    assert result["foo"] == "bar"
    assert "optional" not in result


# Test get_path_params


@pytest.mark.asyncio
async def test_get_path_params_extracts_params():
    """Should extract path parameters."""

    async def receive():
        return {"type": "http.request"}

    # Starlette stores path params in the scope during routing
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/user/123",
            "path_params": {"user_id": "123", "action": "view"},
        },
        receive,
    )

    result = await utils.get_path_params(request, args=["user_id", "action"])

    assert isinstance(result, dict)
    assert result["user_id"] == "123"
    assert result["action"] == "view"


@pytest.mark.asyncio
async def test_get_path_params_missing_returns_error():
    """Should return error for missing path params."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "path_params": {"user_id": "123"}},
        receive,
    )

    result = await utils.get_path_params(request, args=["user_id", "missing"])

    assert isinstance(result, PlainTextResponse)
    assert result.status_code == 400


# Test get_headers


@pytest.mark.asyncio
async def test_get_headers_extracts_headers():
    """Should extract headers."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "headers": [
                [b"content-type", b"application/json"],
                [b"x-custom", b"value"],
            ],
        },
        receive,
    )

    result = await utils.get_headers(
        request, args=["content-type", "x-custom"]
    )

    assert isinstance(result, dict)
    assert result["content-type"] == "application/json"
    assert result["x-custom"] == "value"


@pytest.mark.asyncio
async def test_get_headers_missing_returns_error():
    """Should return error for missing headers."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "headers": [[b"content-type", b"application/json"]],
        },
        receive,
    )

    result = await utils.get_headers(request, args=["content-type", "missing"])

    assert isinstance(result, PlainTextResponse)
    assert result.status_code == 400


# Test convert_for_json


def test_convert_for_json_converts_datetime():
    """Should convert datetime to timestamp."""
    dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = utils._convert_for_json(dt)
    assert isinstance(result, int)
    assert result == int(dt.timestamp())


def test_convert_for_json_converts_date():
    """Should convert date to timestamp."""
    d = date(2024, 1, 1)
    result = utils._convert_for_json(d)
    assert isinstance(result, int)


def test_convert_for_json_converts_nested_dict():
    """Should recursively convert nested structures."""
    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    data = {"timestamp": dt, "nested": {"value": 123}}
    result = utils._convert_for_json(data)
    assert isinstance(result["timestamp"], int)
    assert result["nested"]["value"] == 123


def test_convert_for_json_converts_list():
    """Should convert lists."""
    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    data = [dt, "string", 123]
    result = utils._convert_for_json(data)
    assert isinstance(result[0], int)
    assert result[1] == "string"
    assert result[2] == 123


def test_convert_for_json_converts_tuple():
    """Should convert tuples."""
    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    data = (dt, "string", 123)
    result = utils._convert_for_json(data)
    assert isinstance(result[0], int)
    assert result[1] == "string"
    assert result[2] == 123


def test_convert_for_json_handles_infinity_in_dataframe():
    """Should convert infinity to None in DataFrames."""
    df = pl.DataFrame({"value": [1.0, np.inf, 3.0]})
    result = utils._convert_for_json(df)
    assert result[0]["value"] == 1.0
    assert result[1]["value"] is None
    assert result[2]["value"] == 3.0


def test_convert_for_json_handles_negative_infinity_in_dataframe():
    """Should convert -infinity to None in DataFrames."""
    df = pl.DataFrame({"value": [1.0, -np.inf, 3.0]})
    result = utils._convert_for_json(df)
    assert result[0]["value"] == 1.0
    assert result[1]["value"] is None
    assert result[2]["value"] == 3.0


def test_convert_for_json_handles_regular_dataframe():
    """Should convert regular DataFrames correctly."""
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    result = utils._convert_for_json(df)
    assert len(result) == 3
    assert result[0]["a"] == 1
    assert result[0]["b"] == "x"


def test_convert_for_json_preserves_primitives():
    """Should preserve primitive types."""
    assert utils._convert_for_json(123) == 123
    assert utils._convert_for_json("string") == "string"
    assert utils._convert_for_json(3.14) == 3.14
    assert utils._convert_for_json(True) is True
    assert utils._convert_for_json(None) is None


# Test JSONResponse


def test_json_response_creates_response():
    """Should create JSONResponse."""
    data = {"foo": "bar"}
    response = utils.JSONResponse(data)
    assert isinstance(response, Response)
    assert response.status_code == 200


def test_json_response_converts_data():
    """Should convert data before creating response."""
    dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
    data = {"timestamp": dt}
    response = utils.JSONResponse(data)
    # Parse the body to check conversion
    assert isinstance(response.body, bytes)
    body = json.loads(response.body.decode())
    assert isinstance(body["timestamp"], int)


# Test decorators


@pytest.mark.asyncio
async def test_with_json_params_decorator():
    """with_json_params decorator should extract and pass params."""

    @utils.with_json_params(args=["foo", "baz"])
    async def handler(req: Request, foo: str, baz: int) -> Response:
        return Response(content=f"{foo}-{baz}")

    async def receive():
        return {
            "body": json.dumps({"foo": "bar", "baz": 123}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    response = await handler(request)

    assert response.body.decode() == "bar-123"


@pytest.mark.asyncio
async def test_with_json_params_decorator_missing_param_returns_error():
    """Decorator should return error for missing params."""

    @utils.with_json_params(args=["foo", "missing"])
    async def handler(req: Request, **kwargs) -> Response:
        return Response(content="success")

    async def receive():
        return {
            "body": json.dumps({"foo": "bar"}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    response = await handler(request)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_with_json_params_decorator_replaces_hyphens():
    """Decorator should replace hyphens with underscores."""

    @utils.with_json_params(args=["foo-bar"])
    async def handler(req: Request, foo_bar: str) -> Response:
        return Response(content=foo_bar)

    async def receive():
        return {
            "body": json.dumps({"foo-bar": "value"}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    response = await handler(request)

    assert response.body.decode() == "value"


@pytest.mark.asyncio
async def test_with_query_string_params_decorator():
    """with_query_string_params decorator should work."""

    @utils.with_query_string_params(args=["foo"])
    async def handler(req: Request, foo: str) -> Response:
        return Response(content=foo)

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "query_string": b"foo=bar"}, receive
    )
    response = await handler(request)

    assert response.body.decode() == "bar"


@pytest.mark.asyncio
async def test_with_path_params_decorator():
    """with_path_params decorator should work."""

    @utils.with_path_params(args=["id"])
    async def handler(req: Request, id: str) -> Response:
        return Response(content=id)

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "path_params": {"id": "123"}},
        receive,
    )

    response = await handler(request)

    assert response.body.decode() == "123"


@pytest.mark.asyncio
async def test_with_headers_decorator():
    """with_headers decorator should work."""

    @utils.with_headers(args=["x-custom"])
    async def handler(req: Request, x_custom: str) -> Response:
        return Response(content=x_custom)

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "headers": [[b"x-custom", b"value"]],
        },
        receive,
    )

    response = await handler(request)

    assert response.body.decode() == "value"


# Test decorator with single string arg


@pytest.mark.asyncio
async def test_with_json_params_single_string_arg():
    """Decorator should accept single string argument."""

    @utils.with_json_params(args="foo")
    async def handler(req: Request, foo: str) -> Response:
        return Response(content=foo)

    async def receive():
        return {
            "body": json.dumps({"foo": "bar"}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    response = await handler(request)

    assert response.body.decode() == "bar"


@pytest.mark.asyncio
async def test_with_json_params_optional_single_string():
    """Decorator should accept single string optional argument."""

    @utils.with_json_params(args="foo", opt_args="optional")
    async def handler(
        req: Request, foo: str, optional: str | None = None
    ) -> Response:
        return Response(content=f"{foo}-{optional}")

    async def receive():
        return {
            "body": json.dumps({"foo": "bar"}).encode(),
            "type": "http.request",
        }

    request = Request({"type": "http", "method": "POST"}, receive)
    response = await handler(request)

    assert response.body.decode() == "bar-None"


# Test functions with None args (for coverage of default args assignment)


@pytest.mark.asyncio
async def test_get_query_string_params_with_none_args():
    """Should handle None args gracefully."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "query_string": b"foo=bar"}, receive
    )
    result = await utils.get_query_string_params(request, args=None)

    assert isinstance(result, dict)
    assert result == {}


@pytest.mark.asyncio
async def test_get_path_params_with_none_args():
    """Should handle None args gracefully."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "path_params": {"id": "123"}},
        receive,
    )
    result = await utils.get_path_params(request, args=None)

    assert isinstance(result, dict)
    assert result == {}


@pytest.mark.asyncio
async def test_get_headers_with_none_args():
    """Should handle None args gracefully."""

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "headers": [[b"content-type", b"application/json"]],
        },
        receive,
    )
    result = await utils.get_headers(request, args=None)

    assert isinstance(result, dict)
    assert result == {}


# Test error return paths in decorators


@pytest.mark.asyncio
async def test_with_query_string_params_decorator_error_path():
    """Decorator should return error response when params missing."""

    @utils.with_query_string_params(args=["required"])
    async def handler(req: Request, required: str) -> Response:
        return Response(content="success")

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "query_string": b""}, receive
    )
    response = await handler(request)

    assert isinstance(response, PlainTextResponse)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_with_path_params_decorator_error_path():
    """Decorator should return error response when params missing."""

    @utils.with_path_params(args=["required"])
    async def handler(req: Request, required: str) -> Response:
        return Response(content="success")

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "path_params": {}}, receive
    )
    response = await handler(request)

    assert isinstance(response, PlainTextResponse)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_with_headers_decorator_error_path():
    """Decorator should return error response when headers missing."""

    @utils.with_headers(args=["required"])
    async def handler(req: Request, required: str) -> Response:
        return Response(content="success")

    async def receive():
        return {"type": "http.request"}

    request = Request(
        {"type": "http", "method": "GET", "headers": []}, receive
    )
    response = await handler(request)

    assert isinstance(response, PlainTextResponse)
    assert response.status_code == 400
