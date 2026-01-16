"""Tests for ChatKit asset proxy helpers."""

from __future__ import annotations
from typing import Any
import pytest
from fastapi import HTTPException, status
from starlette.requests import Request
from orcheo_backend.app.chatkit_asset_proxy import (
    _RESPONSE_HEADER_ALLOWLIST,
    _inject_fetch_guard,
    _normalize_path_prefix,
    _sanitize_asset_path,
    proxy_chatkit_asset,
)


async def _empty_receive() -> dict[str, Any]:
    """Provide a no-op HTTP receive coroutine for ASGI Request objects."""
    return {"type": "http.request", "body": b"", "more_body": False}


def _make_proxy_request(*, method: str = "GET", path: str = "/") -> Request:
    """Create a mock Starlette Request for proxy testing."""
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [],
        "root_path": "",
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope, _empty_receive)


def testresponse_header_allowlist_includes_content_range() -> None:
    """Content-Range is preserved for partial responses."""
    assert "content-range" in _RESPONSE_HEADER_ALLOWLIST


def test_normalize_path_prefix_empty_string() -> None:
    """Empty string normalizes to root slash."""
    assert _normalize_path_prefix("") == "/"


def test_normalize_path_prefix_whitespace_only() -> None:
    """Whitespace-only string normalizes to root slash."""
    assert _normalize_path_prefix("   ") == "/"


def test_normalize_path_prefix_no_leading_slash() -> None:
    """Path without leading slash gets one added."""
    assert _normalize_path_prefix("assets/ck1") == "/assets/ck1/"


def test_normalize_path_prefix_no_trailing_slash() -> None:
    """Path without trailing slash gets one added."""
    assert _normalize_path_prefix("/assets/ck1") == "/assets/ck1/"


def test_normalize_path_prefix_already_normalized() -> None:
    """Fully normalized path is returned unchanged."""
    assert _normalize_path_prefix("/assets/ck1/") == "/assets/ck1/"


def test_sanitize_asset_path_rejects_path_traversal() -> None:
    """Path traversal attempts are rejected with 404."""
    with pytest.raises(HTTPException) as excinfo:
        _sanitize_asset_path("foo/../bar")
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND


def test_sanitize_asset_path_rejects_empty_path() -> None:
    """Empty paths are rejected with 404."""
    with pytest.raises(HTTPException) as excinfo:
        _sanitize_asset_path("")
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND


def test_sanitize_asset_path_valid_path() -> None:
    """Valid paths are cleaned and returned."""
    assert _sanitize_asset_path("/foo/bar.js/") == "foo/bar.js"


def test_inject_fetch_guard_skips_already_guarded() -> None:
    """HTML with existing guard is returned unchanged."""
    html = "<head data-orcheo-fetch-guard><script>test</script></head>"
    assert _inject_fetch_guard(html) == html


def test_inject_fetch_guard_no_head_tag() -> None:
    """HTML without head tag is returned unchanged."""
    html = "<body><div>content</div></body>"
    assert _inject_fetch_guard(html) == html


def test_inject_fetch_guard_inserts_after_head() -> None:
    """Guard script is inserted after opening head tag."""
    html = "<head><title>Test</title></head>"
    result = _inject_fetch_guard(html)
    assert "data-orcheo-fetch-guard" in result
    assert result.index("data-orcheo-fetch-guard") < result.index("<title>")


@pytest.mark.asyncio
async def test_proxy_chatkit_asset_rejects_non_get_head_methods() -> None:
    """Non-GET/HEAD methods raise 405 Method Not Allowed."""
    request = _make_proxy_request(method="POST", path="/assets/ck1/index.js")
    with pytest.raises(HTTPException) as excinfo:
        await proxy_chatkit_asset(request, prefix="assets/ck1", asset_path="index.js")
    assert excinfo.value.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
