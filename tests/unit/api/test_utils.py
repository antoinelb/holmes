"""Unit tests for holmes.api.utils module."""

from datetime import date, datetime
from unittest.mock import AsyncMock

import numpy as np
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

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


class TestConvertForJson:
    """Tests for convert_for_json function."""

    def test_convert_for_json_polars_dataframe(self):
        """DataFrame conversion returns list of dicts."""
        df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        result = convert_for_json(df)
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0] == {"a": 1, "b": "x"}
        assert result[1] == {"a": 2, "b": "y"}
        assert result[2] == {"a": 3, "b": "z"}

    def test_convert_for_json_datetime(self):
        """Datetime handling returns timestamp."""
        dt = datetime(2023, 6, 15, 12, 30, 0)
        result = convert_for_json(dt)
        assert isinstance(result, int)
        # Verify it's a reasonable timestamp
        assert result > 0

    def test_convert_for_json_date(self):
        """Date handling returns timestamp."""
        d = date(2023, 6, 15)
        result = convert_for_json(d)
        assert isinstance(result, int)
        assert result > 0

    def test_convert_for_json_nan(self):
        """NaN to null conversion."""
        result = convert_for_json(float("nan"))
        assert result is None

    def test_convert_for_json_inf(self):
        """Infinity values in DataFrame are converted to None."""
        df = pl.DataFrame({"a": [1.0, float("inf"), 3.0]})
        result = convert_for_json(df)
        assert result[0]["a"] == 1.0
        assert result[1]["a"] is None
        assert result[2]["a"] == 3.0

    def test_convert_for_json_numpy_array(self):
        """Array to list conversion."""
        arr = np.array([1, 2, 3, 4, 5])
        result = convert_for_json(arr)
        assert isinstance(result, list)
        assert result == [1, 2, 3, 4, 5]

    def test_convert_for_json_nested(self):
        """Nested structures are converted recursively."""
        data = {
            "array": np.array([1, 2]),
            "datetime": datetime(2023, 1, 1, 0, 0),
            "nested": {"value": float("nan")},
        }
        result = convert_for_json(data)
        assert isinstance(result["array"], list)
        assert isinstance(result["datetime"], int)
        assert result["nested"]["value"] is None

    def test_convert_for_json_list(self):
        """Lists are converted recursively."""
        data = [np.array([1]), float("nan"), datetime(2023, 1, 1)]
        result = convert_for_json(data)
        assert result[0] == [1]
        assert result[1] is None
        assert isinstance(result[2], int)

    def test_convert_for_json_tuple(self):
        """Tuples are converted to lists recursively."""
        data = (np.array([1, 2]), float("nan"))
        result = convert_for_json(data)
        assert isinstance(result, list)
        assert result[0] == [1, 2]
        assert result[1] is None

    def test_convert_for_json_regular_float(self):
        """Regular floats pass through unchanged."""
        result = convert_for_json(3.14159)
        assert result == 3.14159

    def test_convert_for_json_string(self):
        """Strings pass through unchanged."""
        result = convert_for_json("hello")
        assert result == "hello"

    def test_convert_for_json_none(self):
        """None passes through unchanged."""
        result = convert_for_json(None)
        assert result is None

    def test_convert_for_json_dataframe_with_dates(self):
        """DataFrame with Date column converts to string format."""
        df = pl.DataFrame(
            {"date": [date(2023, 1, 15), date(2023, 6, 30)], "value": [1, 2]}
        )
        result = convert_for_json(df)
        assert result[0]["date"] == "2023-01-15"
        assert result[1]["date"] == "2023-06-30"

    def test_convert_for_json_dataframe_with_datetime(self):
        """DataFrame with Datetime column converts to string format."""
        df = pl.DataFrame(
            {
                "datetime": [
                    datetime(2023, 1, 15, 10, 30, 0),
                    datetime(2023, 6, 30, 14, 45, 30),
                ],
                "value": [1, 2],
            }
        )
        result = convert_for_json(df)
        assert result[0]["datetime"] == "2023-01-15 10:30:00"
        assert result[1]["datetime"] == "2023-06-30 14:45:30"

    def test_convert_for_json_dataframe_negative_inf(self):
        """Negative infinity values in DataFrame are converted to None."""
        df = pl.DataFrame({"a": [1.0, float("-inf"), 3.0]})
        result = convert_for_json(df)
        assert result[0]["a"] == 1.0
        assert result[1]["a"] is None
        assert result[2]["a"] == 3.0


class TestHypothesis:
    """Property-based tests for convert_for_json."""

    @given(st.integers())
    @settings(max_examples=50)
    def test_integers_pass_through(self, value):
        """Integers pass through unchanged."""
        result = convert_for_json(value)
        assert result == value

    @given(
        st.floats(
            allow_nan=False,
            allow_infinity=False,
            min_value=-1e10,
            max_value=1e10,
        )
    )
    @settings(max_examples=50)
    def test_regular_floats_pass_through(self, value):
        """Regular floats pass through unchanged."""
        result = convert_for_json(value)
        assert result == value

    @given(st.lists(st.integers(), min_size=0, max_size=10))
    @settings(max_examples=50)
    def test_integer_lists_pass_through(self, value):
        """Lists of integers pass through as lists."""
        result = convert_for_json(value)
        assert result == value

    @given(st.dictionaries(st.text(min_size=1, max_size=5), st.integers()))
    @settings(max_examples=50)
    def test_integer_dicts_pass_through(self, value):
        """Dicts with integer values pass through."""
        result = convert_for_json(value)
        assert result == value

    @given(
        st.lists(
            st.floats(
                allow_nan=False,
                allow_infinity=False,
                min_value=-1e6,
                max_value=1e6,
            ),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=50)
    def test_numpy_arrays_become_lists(self, values):
        """Numpy arrays become Python lists."""
        arr = np.array(values)
        result = convert_for_json(arr)
        assert isinstance(result, list)
        assert len(result) == len(values)


class TestGetJsonParams:
    """Tests for get_json_params function."""

    @pytest.mark.asyncio
    async def test_get_json_params_valid(self):
        """Valid JSON with required params returns dict."""
        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"name": "test", "value": 42}'

        result = await get_json_params(request, args=["name", "value"])

        assert result == {"name": "test", "value": 42}

    @pytest.mark.asyncio
    async def test_get_json_params_with_optional(self):
        """Optional params are included when present."""
        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"name": "test", "optional": "yes"}'

        result = await get_json_params(
            request, args=["name"], opt_args=["optional"]
        )

        assert result == {"name": "test", "optional": "yes"}

    @pytest.mark.asyncio
    async def test_get_json_params_optional_missing(self):
        """Missing optional params are not included."""
        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"name": "test"}'

        result = await get_json_params(
            request, args=["name"], opt_args=["optional"]
        )

        assert result == {"name": "test"}

    @pytest.mark.asyncio
    async def test_get_json_params_invalid_json(self):
        """Invalid JSON returns 400 error."""
        request = AsyncMock(spec=Request)
        request.body.return_value = b"not json"

        result = await get_json_params(request, args=["name"])

        assert isinstance(result, PlainTextResponse)
        assert result.status_code == 400
        assert result.body == b"Wrong data type was sent."

    @pytest.mark.asyncio
    async def test_get_json_params_missing_required(self):
        """Missing required param returns 400 error."""
        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"other": "value"}'

        result = await get_json_params(request, args=["name"])

        assert isinstance(result, PlainTextResponse)
        assert result.status_code == 400
        assert result.body == b"There are missing parameters."

    @pytest.mark.asyncio
    async def test_get_json_params_no_args(self):
        """Empty args list returns empty dict."""
        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"name": "test"}'

        result = await get_json_params(request)

        assert result == {}


class TestGetQueryStringParams:
    """Tests for get_query_string_params function."""

    @pytest.mark.asyncio
    async def test_get_query_string_params_valid(self):
        """Valid query params returns dict."""
        request = AsyncMock(spec=Request)
        request.query_params = {"name": "test", "value": "42"}

        result = await get_query_string_params(request, args=["name", "value"])

        assert result == {"name": "test", "value": "42"}

    @pytest.mark.asyncio
    async def test_get_query_string_params_with_optional(self):
        """Optional params are included when present."""
        request = AsyncMock(spec=Request)
        request.query_params = {"name": "test", "optional": "yes"}

        result = await get_query_string_params(
            request, args=["name"], opt_args=["optional"]
        )

        assert result == {"name": "test", "optional": "yes"}

    @pytest.mark.asyncio
    async def test_get_query_string_params_optional_missing(self):
        """Missing optional params are not included."""
        request = AsyncMock(spec=Request)
        request.query_params = {"name": "test"}

        result = await get_query_string_params(
            request, args=["name"], opt_args=["optional"]
        )

        assert result == {"name": "test"}

    @pytest.mark.asyncio
    async def test_get_query_string_params_missing_required(self):
        """Missing required param returns 400 error."""
        request = AsyncMock(spec=Request)
        request.query_params = {"other": "value"}

        result = await get_query_string_params(request, args=["name"])

        assert isinstance(result, PlainTextResponse)
        assert result.status_code == 400
        assert result.body == b"There are missing parameters."

    @pytest.mark.asyncio
    async def test_get_query_string_params_no_args(self):
        """Empty args list returns empty dict."""
        request = AsyncMock(spec=Request)
        request.query_params = {"name": "test"}

        result = await get_query_string_params(request)

        assert result == {}


class TestGetPathParams:
    """Tests for get_path_params function."""

    @pytest.mark.asyncio
    async def test_get_path_params_valid(self):
        """Valid path params returns dict."""
        request = AsyncMock(spec=Request)
        request.path_params = {"id": "123", "name": "test"}

        result = await get_path_params(request, args=["id", "name"])

        assert result == {"id": "123", "name": "test"}

    @pytest.mark.asyncio
    async def test_get_path_params_with_optional(self):
        """Optional params are included when present."""
        request = AsyncMock(spec=Request)
        request.path_params = {"id": "123", "slug": "my-slug"}

        result = await get_path_params(
            request, args=["id"], opt_args=["slug"]
        )

        assert result == {"id": "123", "slug": "my-slug"}

    @pytest.mark.asyncio
    async def test_get_path_params_optional_missing(self):
        """Missing optional params are not included."""
        request = AsyncMock(spec=Request)
        request.path_params = {"id": "123"}

        result = await get_path_params(
            request, args=["id"], opt_args=["slug"]
        )

        assert result == {"id": "123"}

    @pytest.mark.asyncio
    async def test_get_path_params_missing_required(self):
        """Missing required param returns 400 error."""
        request = AsyncMock(spec=Request)
        request.path_params = {"other": "value"}

        result = await get_path_params(request, args=["id"])

        assert isinstance(result, PlainTextResponse)
        assert result.status_code == 400
        assert result.body == b"There are missing parameters."

    @pytest.mark.asyncio
    async def test_get_path_params_no_args(self):
        """Empty args list returns empty dict."""
        request = AsyncMock(spec=Request)
        request.path_params = {"id": "123"}

        result = await get_path_params(request)

        assert result == {}


class TestGetHeaders:
    """Tests for get_headers function."""

    @pytest.mark.asyncio
    async def test_get_headers_valid(self):
        """Valid headers returns dict."""
        request = AsyncMock(spec=Request)
        request.headers = {"authorization": "Bearer token", "content-type": "application/json"}

        result = await get_headers(request, args=["authorization", "content-type"])

        assert result == {"authorization": "Bearer token", "content-type": "application/json"}

    @pytest.mark.asyncio
    async def test_get_headers_with_optional(self):
        """Optional headers are included when present."""
        request = AsyncMock(spec=Request)
        request.headers = {"authorization": "Bearer token", "x-custom": "value"}

        result = await get_headers(
            request, args=["authorization"], opt_args=["x-custom"]
        )

        assert result == {"authorization": "Bearer token", "x-custom": "value"}

    @pytest.mark.asyncio
    async def test_get_headers_optional_missing(self):
        """Missing optional headers are not included."""
        request = AsyncMock(spec=Request)
        request.headers = {"authorization": "Bearer token"}

        result = await get_headers(
            request, args=["authorization"], opt_args=["x-custom"]
        )

        assert result == {"authorization": "Bearer token"}

    @pytest.mark.asyncio
    async def test_get_headers_missing_required(self):
        """Missing required header returns 400 error."""
        request = AsyncMock(spec=Request)
        request.headers = {"other": "value"}

        result = await get_headers(request, args=["authorization"])

        assert isinstance(result, PlainTextResponse)
        assert result.status_code == 400
        assert result.body == b"There are missing headers."

    @pytest.mark.asyncio
    async def test_get_headers_no_args(self):
        """Empty args list returns empty dict."""
        request = AsyncMock(spec=Request)
        request.headers = {"authorization": "Bearer token"}

        result = await get_headers(request)

        assert result == {}


class TestWithJsonParams:
    """Tests for with_json_params decorator."""

    @pytest.mark.asyncio
    async def test_with_json_params_list_args(self):
        """Decorator with list args extracts params."""
        @with_json_params(args=["name", "value"])
        async def handler(request, name=None, value=None):
            return PlainTextResponse(f"{name}:{value}")

        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"name": "test", "value": "42"}'

        response = await handler(request)

        assert response.body == b"test:42"

    @pytest.mark.asyncio
    async def test_with_json_params_string_arg(self):
        """Decorator with string arg extracts single param."""
        @with_json_params(args="name")
        async def handler(request, name=None):
            return PlainTextResponse(f"{name}")

        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"name": "test"}'

        response = await handler(request)

        assert response.body == b"test"

    @pytest.mark.asyncio
    async def test_with_json_params_string_opt_arg(self):
        """Decorator with string opt_arg extracts optional param."""
        @with_json_params(opt_args="optional")
        async def handler(request, optional=None):
            return PlainTextResponse(f"{optional}")

        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"optional": "yes"}'

        response = await handler(request)

        assert response.body == b"yes"

    @pytest.mark.asyncio
    async def test_with_json_params_hyphen_to_underscore(self):
        """Decorator converts hyphens to underscores in param names."""
        @with_json_params(args=["my-param"])
        async def handler(request, my_param=None):
            return PlainTextResponse(f"{my_param}")

        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"my-param": "test"}'

        response = await handler(request)

        assert response.body == b"test"

    @pytest.mark.asyncio
    async def test_with_json_params_returns_error(self):
        """Decorator returns error response when params missing."""
        @with_json_params(args=["name"])
        async def handler(request, name=None):
            return PlainTextResponse(f"{name}")

        request = AsyncMock(spec=Request)
        request.body.return_value = b'{"other": "value"}'

        response = await handler(request)

        assert response.status_code == 400


class TestWithQueryStringParams:
    """Tests for with_query_string_params decorator."""

    @pytest.mark.asyncio
    async def test_with_query_string_params_list_args(self):
        """Decorator with list args extracts params."""
        @with_query_string_params(args=["name", "value"])
        async def handler(request, name=None, value=None):
            return PlainTextResponse(f"{name}:{value}")

        request = AsyncMock(spec=Request)
        request.query_params = {"name": "test", "value": "42"}

        response = await handler(request)

        assert response.body == b"test:42"

    @pytest.mark.asyncio
    async def test_with_query_string_params_string_arg(self):
        """Decorator with string arg extracts single param."""
        @with_query_string_params(args="name")
        async def handler(request, name=None):
            return PlainTextResponse(f"{name}")

        request = AsyncMock(spec=Request)
        request.query_params = {"name": "test"}

        response = await handler(request)

        assert response.body == b"test"

    @pytest.mark.asyncio
    async def test_with_query_string_params_string_opt_arg(self):
        """Decorator with string opt_arg extracts optional param."""
        @with_query_string_params(opt_args="optional")
        async def handler(request, optional=None):
            return PlainTextResponse(f"{optional}")

        request = AsyncMock(spec=Request)
        request.query_params = {"optional": "yes"}

        response = await handler(request)

        assert response.body == b"yes"

    @pytest.mark.asyncio
    async def test_with_query_string_params_hyphen_to_underscore(self):
        """Decorator converts hyphens to underscores in param names."""
        @with_query_string_params(args=["my-param"])
        async def handler(request, my_param=None):
            return PlainTextResponse(f"{my_param}")

        request = AsyncMock(spec=Request)
        request.query_params = {"my-param": "test"}

        response = await handler(request)

        assert response.body == b"test"

    @pytest.mark.asyncio
    async def test_with_query_string_params_returns_error(self):
        """Decorator returns error response when params missing."""
        @with_query_string_params(args=["name"])
        async def handler(request, name=None):
            return PlainTextResponse(f"{name}")

        request = AsyncMock(spec=Request)
        request.query_params = {"other": "value"}

        response = await handler(request)

        assert response.status_code == 400


class TestWithPathParams:
    """Tests for with_path_params decorator."""

    @pytest.mark.asyncio
    async def test_with_path_params_list_args(self):
        """Decorator with list args extracts params."""
        @with_path_params(args=["id", "name"])
        async def handler(request, id=None, name=None):
            return PlainTextResponse(f"{id}:{name}")

        request = AsyncMock(spec=Request)
        request.path_params = {"id": "123", "name": "test"}

        response = await handler(request)

        assert response.body == b"123:test"

    @pytest.mark.asyncio
    async def test_with_path_params_string_arg(self):
        """Decorator with string arg extracts single param."""
        @with_path_params(args="id")
        async def handler(request, id=None):
            return PlainTextResponse(f"{id}")

        request = AsyncMock(spec=Request)
        request.path_params = {"id": "123"}

        response = await handler(request)

        assert response.body == b"123"

    @pytest.mark.asyncio
    async def test_with_path_params_string_opt_arg(self):
        """Decorator with string opt_arg extracts optional param."""
        @with_path_params(opt_args="slug")
        async def handler(request, slug=None):
            return PlainTextResponse(f"{slug}")

        request = AsyncMock(spec=Request)
        request.path_params = {"slug": "my-slug"}

        response = await handler(request)

        assert response.body == b"my-slug"

    @pytest.mark.asyncio
    async def test_with_path_params_hyphen_to_underscore(self):
        """Decorator converts hyphens to underscores in param names."""
        @with_path_params(args=["my-id"])
        async def handler(request, my_id=None):
            return PlainTextResponse(f"{my_id}")

        request = AsyncMock(spec=Request)
        request.path_params = {"my-id": "123"}

        response = await handler(request)

        assert response.body == b"123"

    @pytest.mark.asyncio
    async def test_with_path_params_returns_error(self):
        """Decorator returns error response when params missing."""
        @with_path_params(args=["id"])
        async def handler(request, id=None):
            return PlainTextResponse(f"{id}")

        request = AsyncMock(spec=Request)
        request.path_params = {"other": "value"}

        response = await handler(request)

        assert response.status_code == 400


class TestWithHeaders:
    """Tests for with_headers decorator."""

    @pytest.mark.asyncio
    async def test_with_headers_list_args(self):
        """Decorator with list args extracts headers."""
        @with_headers(args=["authorization", "content-type"])
        async def handler(request, authorization=None, content_type=None):
            return PlainTextResponse(f"{authorization}:{content_type}")

        request = AsyncMock(spec=Request)
        request.headers = {"authorization": "Bearer", "content-type": "json"}

        response = await handler(request)

        assert response.body == b"Bearer:json"

    @pytest.mark.asyncio
    async def test_with_headers_string_arg(self):
        """Decorator with string arg extracts single header."""
        @with_headers(args="authorization")
        async def handler(request, authorization=None):
            return PlainTextResponse(f"{authorization}")

        request = AsyncMock(spec=Request)
        request.headers = {"authorization": "Bearer token"}

        response = await handler(request)

        assert response.body == b"Bearer token"

    @pytest.mark.asyncio
    async def test_with_headers_string_opt_arg(self):
        """Decorator with string opt_arg extracts optional header."""
        @with_headers(opt_args="x-custom")
        async def handler(request, x_custom=None):
            return PlainTextResponse(f"{x_custom}")

        request = AsyncMock(spec=Request)
        request.headers = {"x-custom": "value"}

        response = await handler(request)

        assert response.body == b"value"

    @pytest.mark.asyncio
    async def test_with_headers_hyphen_to_underscore(self):
        """Decorator converts hyphens to underscores in header names."""
        @with_headers(args=["x-api-key"])
        async def handler(request, x_api_key=None):
            return PlainTextResponse(f"{x_api_key}")

        request = AsyncMock(spec=Request)
        request.headers = {"x-api-key": "secret"}

        response = await handler(request)

        assert response.body == b"secret"

    @pytest.mark.asyncio
    async def test_with_headers_returns_error(self):
        """Decorator returns error response when headers missing."""
        @with_headers(args=["authorization"])
        async def handler(request, authorization=None):
            return PlainTextResponse(f"{authorization}")

        request = AsyncMock(spec=Request)
        request.headers = {"other": "value"}

        response = await handler(request)

        assert response.status_code == 400


class TestJSONResponse:
    """Tests for JSONResponse function."""

    def test_json_response_basic(self):
        """JSONResponse returns proper JSON response."""
        response = JSONResponse({"key": "value"})
        assert response.status_code == 200
        assert b'"key":"value"' in response.body

    def test_json_response_with_conversion(self):
        """JSONResponse converts non-JSON types."""
        response = JSONResponse({"array": np.array([1, 2, 3])})
        assert b'"array":[1,2,3]' in response.body

    def test_json_response_with_status_code(self):
        """JSONResponse accepts status_code argument."""
        response = JSONResponse({"error": "not found"}, status_code=404)
        assert response.status_code == 404


class TestSend:
    """Tests for send function."""

    @pytest.mark.asyncio
    async def test_send_basic(self):
        """Send sends JSON message to WebSocket."""
        ws = AsyncMock(spec=WebSocket)

        await send(ws, "test_event", {"value": 42})

        ws.send_json.assert_called_once_with({
            "type": "test_event",
            "data": {"value": 42},
        })

    @pytest.mark.asyncio
    async def test_send_with_conversion(self):
        """Send converts data before sending."""
        ws = AsyncMock(spec=WebSocket)

        await send(ws, "data", {"array": np.array([1, 2])})

        ws.send_json.assert_called_once_with({
            "type": "data",
            "data": {"array": [1, 2]},
        })
