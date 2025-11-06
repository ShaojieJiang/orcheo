"""API client error handling tests for the CLI."""

from __future__ import annotations
import httpx
import pytest
import respx
from orcheo_sdk.cli.errors import APICallError
from orcheo_sdk.cli.http import ApiClient


def test_api_client_error_with_nested_message() -> None:
    """Test error formatting with nested detail.message structure."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"message": "Nested error message"}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    assert "Nested error message" in str(exc_info.value)


def test_api_client_error_with_detail_detail() -> None:
    """Test error formatting with detail.detail structure."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"detail": "Detail in detail field"}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    assert "Detail in detail field" in str(exc_info.value)


def test_api_client_error_with_message_field() -> None:
    """Test error formatting with top-level message field."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.post("http://test.com/api/test").mock(
            return_value=httpx.Response(500, json={"message": "Server error message"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.post("/api/test", json_body={})
    assert "Server error message" in str(exc_info.value)


def test_api_client_error_with_detail_as_string() -> None:
    """Test error formatting when detail is a string, not a mapping."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(400, json={"detail": "Simple error string"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail is not a Mapping, should fall through to response.text
    assert exc_info.value.status_code == 400


def test_api_client_error_with_empty_message_in_detail() -> None:
    """Test error formatting when detail.message and detail.detail are both empty."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"message": None, "detail": None}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When message is None/empty, should check "message" in payload
    assert exc_info.value.status_code == 400


def test_api_client_error_with_detail_missing_message_field() -> None:
    """Test error formatting when detail Mapping has no message/detail fields."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400, json={"detail": {"some_other_field": "value"}}
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail has no message/detail fields, fall through to response.text
    assert exc_info.value.status_code == 400


def test_api_client_error_with_non_mapping_detail_no_message() -> None:
    """Test error formatting when detail is not a Mapping and no message field."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(400, json={"detail": "error string"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail is not Mapping and no message, falls through to response.text
    assert exc_info.value.status_code == 400


def test_api_client_error_with_no_detail_no_message() -> None:
    """Test error formatting when payload has neither detail nor message."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(400, json={"error": "something"})
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When no detail and no message fields, falls through to response.text
    assert exc_info.value.status_code == 400


def test_api_client_error_detail_mapping_no_message_value() -> None:
    """Test error formatting when detail is Mapping with no valid message value."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400,
                json={"detail": {"message": "", "detail": ""}},
                text='{"detail": {"message": "", "detail": ""}}',
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail.message and detail.detail are empty strings (falsy but present)
    # Should fall through to checking "message" in payload, then to response.text
    assert exc_info.value.status_code == 400
    assert '{"detail"' in str(exc_info.value)


def test_api_client_error_detail_not_mapping_no_message() -> None:
    """Test error formatting when detail is not a Mapping and no message field."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400,
                json={"detail": "string detail", "other_field": "value"},
                text='{"detail": "string detail", "other_field": "value"}',
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When detail is not a Mapping and there's no "message" field in payload
    # Should fall through to response.text (line 109)
    assert exc_info.value.status_code == 400
    assert "string detail" in str(exc_info.value)


def test_api_client_error_payload_not_mapping() -> None:
    """Test error formatting when payload itself is not a Mapping."""
    client = ApiClient(base_url="http://test.com", token="token123")
    with respx.mock:
        respx.get("http://test.com/api/test").mock(
            return_value=httpx.Response(
                400,
                json=["error", "list"],
                text='["error", "list"]',
            )
        )
        with pytest.raises(APICallError) as exc_info:
            client.get("/api/test")
    # When payload is not a Mapping (e.g., a list), should go directly to response.text
    # This covers the branch 101->109 where isinstance(payload, Mapping) is False
    assert exc_info.value.status_code == 400
    assert '["error", "list"]' in str(exc_info.value)


def test_api_call_error_with_status_code() -> None:
    error = APICallError("API error", status_code=500)
    assert str(error) == "API error"
    assert error.status_code == 500


def test_api_call_error_without_status_code() -> None:
    error = APICallError("API error")
    assert str(error) == "API error"
    assert error.status_code is None
