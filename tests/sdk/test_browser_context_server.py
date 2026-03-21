"""Tests for browser context HTTP server endpoints."""

from __future__ import annotations
import threading
from datetime import UTC, datetime
from http.server import HTTPServer
import httpx
import pytest
from orcheo_sdk.cli.browser_context.server import create_request_handler
from orcheo_sdk.cli.browser_context.store import BrowserContextStore


def _ts() -> str:
    """Return a fresh ISO 8601 timestamp string."""
    return datetime.now(UTC).isoformat()


@pytest.fixture()
def context_server() -> tuple[str, HTTPServer]:
    """Start a context server on a random port and return (base_url, server)."""
    store = BrowserContextStore()
    handler = create_request_handler(store)
    server = HTTPServer(("localhost", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}", server
    server.shutdown()


def test_get_context_empty(context_server: tuple[str, HTTPServer]) -> None:
    """GET /context on empty store returns null context."""
    base_url, _ = context_server
    resp = httpx.get(f"{base_url}/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] is None
    assert data["total_sessions"] == 0


def test_post_then_get_context(context_server: tuple[str, HTTPServer]) -> None:
    """POST /context then GET /context returns the posted context."""
    base_url, _ = context_server
    payload = {
        "session_id": "tab-1",
        "page": "canvas",
        "workflow_id": "wf-abc",
        "workflow_name": "Test Flow",
        "focused": True,
        "timestamp": _ts(),
    }
    resp = httpx.post(f"{base_url}/context", json=payload)
    assert resp.status_code == 204

    resp = httpx.get(f"{base_url}/context")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "tab-1"
    assert data["page"] == "canvas"
    assert data["workflow_id"] == "wf-abc"
    assert data["total_sessions"] == 1


def test_get_sessions(context_server: tuple[str, HTTPServer]) -> None:
    """GET /context/sessions returns all sessions."""
    base_url, _ = context_server
    for i in range(3):
        httpx.post(
            f"{base_url}/context",
            json={
                "session_id": f"tab-{i}",
                "page": "gallery",
                "workflow_id": None,
                "workflow_name": None,
                "focused": i == 0,
                "timestamp": _ts(),
            },
        )

    resp = httpx.get(f"{base_url}/context/sessions")
    assert resp.status_code == 200
    sessions = resp.json()
    assert len(sessions) == 3


def test_cors_headers_without_origin(context_server: tuple[str, HTTPServer]) -> None:
    """Requests without an Origin header get an empty CORS origin."""
    base_url, _ = context_server
    resp = httpx.get(f"{base_url}/context")
    assert resp.headers["access-control-allow-origin"] == ""


def test_cors_headers_with_localhost_origin(
    context_server: tuple[str, HTTPServer],
) -> None:
    """Requests from a localhost origin are reflected back."""
    base_url, _ = context_server
    origin = "http://localhost:5173"
    resp = httpx.get(f"{base_url}/context", headers={"Origin": origin})
    assert resp.headers["access-control-allow-origin"] == origin


def test_cors_headers_rejects_non_localhost(
    context_server: tuple[str, HTTPServer],
) -> None:
    """Requests from non-localhost origins get an empty CORS origin."""
    base_url, _ = context_server
    resp = httpx.get(f"{base_url}/context", headers={"Origin": "http://evil.com"})
    assert resp.headers["access-control-allow-origin"] == ""


def test_options_preflight(context_server: tuple[str, HTTPServer]) -> None:
    """OPTIONS request returns 204 with CORS headers."""
    base_url, _ = context_server
    resp = httpx.options(f"{base_url}/context")
    assert resp.status_code == 204
    assert "access-control-allow-origin" in resp.headers


def test_post_missing_fields(context_server: tuple[str, HTTPServer]) -> None:
    """POST /context with missing required fields returns 400."""
    base_url, _ = context_server
    resp = httpx.post(f"{base_url}/context", json={"session_id": "x"})
    assert resp.status_code == 400
    data = resp.json()
    assert "missing fields" in data["error"]


def test_post_invalid_json(context_server: tuple[str, HTTPServer]) -> None:
    """POST /context with invalid JSON returns 400."""
    base_url, _ = context_server
    resp = httpx.post(
        f"{base_url}/context",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_post_empty_body(context_server: tuple[str, HTTPServer]) -> None:
    """POST /context with empty body returns 400."""
    base_url, _ = context_server
    resp = httpx.post(
        f"{base_url}/context",
        content=b"",
        headers={"Content-Type": "application/json", "Content-Length": "0"},
    )
    assert resp.status_code == 400


def test_unknown_path(context_server: tuple[str, HTTPServer]) -> None:
    """GET on unknown path returns 404."""
    base_url, _ = context_server
    resp = httpx.get(f"{base_url}/unknown")
    assert resp.status_code == 404


def test_post_unknown_path(context_server: tuple[str, HTTPServer]) -> None:
    """POST on unknown path returns 404."""
    base_url, _ = context_server
    resp = httpx.post(f"{base_url}/unknown", json={})
    assert resp.status_code == 404
