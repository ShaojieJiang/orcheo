import os
import pytest
from fastapi import WebSocketDisconnect
from orcheo_backend.app.workflow_execution import (
    _CANNOT_SEND_AFTER_CLOSE,
    _patched_environment,
    _safe_send_json,
    _sanitize_public_step_payload,
)


class DummyWebSocket:
    def __init__(self, exc: Exception):
        self._exc = exc

    async def send_json(
        self, payload: object
    ) -> None:  # pragma: no cover - exceptions handled
        raise self._exc


def test_patched_environment_restores_previous_value(tmp_path, monkeypatch):
    original = os.environ.get("WORKFLOW_ENV_TEST")
    with _patched_environment({"WORKFLOW_ENV_TEST": "value"}):
        assert os.environ.get("WORKFLOW_ENV_TEST") == "value"
        os.environ["WORKFLOW_ENV_TEST"] = "changed"
    assert os.environ.get("WORKFLOW_ENV_TEST") == original


def test_sanitize_public_step_payload_returns_dict():
    sanitized = _sanitize_public_step_payload({"foo": "bar"})
    assert isinstance(sanitized, dict)
    assert sanitized["foo"] == "bar"


@pytest.mark.asyncio
async def test_safe_send_json_handles_disconnect(monkeypatch):
    websocket = DummyWebSocket(WebSocketDisconnect(code=1000))
    result = await _safe_send_json(websocket, {"status": "ok"})
    assert result is False


@pytest.mark.asyncio
async def test_safe_send_json_handles_closed(monkeypatch):
    socket = DummyWebSocket(RuntimeError(_CANNOT_SEND_AFTER_CLOSE))
    result = await _safe_send_json(socket, {"status": "ok"})
    assert result is False
