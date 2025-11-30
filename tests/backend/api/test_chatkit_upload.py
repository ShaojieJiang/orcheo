"""Security-focused tests for the ChatKit upload endpoint."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from fastapi.testclient import TestClient
import pytest
from orcheo.config import get_settings
from tests.backend.api.shared import backend_app


class _RecordingStore:
    """Test double that records saved attachments."""

    def __init__(self) -> None:
        self.saved: list[tuple[Any, str, Any]] = []

    async def save_attachment(
        self, attachment: Any, context: Any, storage_path: str
    ) -> None:
        self.saved.append((attachment, storage_path, context))


class _RecordingServer:
    """Server double exposing the minimal store interface used by the router."""

    def __init__(self) -> None:
        self.store = _RecordingStore()


@pytest.mark.asyncio
async def test_chatkit_upload_sanitizes_filename(
    api_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upload endpoint should sanitize filenames to prevent traversal."""

    storage_dir = tmp_path / "uploads"
    server = _RecordingServer()

    monkeypatch.setattr(
        backend_app.routers.chatkit, "_resolve_chatkit_server", lambda: server
    )
    monkeypatch.setenv("ORCHEO_CHATKIT_STORAGE_PATH", str(storage_dir))
    get_settings(refresh=True)

    response = api_client.post(
        "/api/chatkit/upload",
        files={"file": ("../../../../etc/passwd", b"payload", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    stored_path = Path(payload["storage_path"]).resolve()
    assert stored_path.is_file()
    assert stored_path.read_bytes() == b"payload"
    assert stored_path.parent == storage_dir.resolve()
    assert payload["name"] == "passwd"
    assert server.store.saved[0][1] == payload["storage_path"]
    monkeypatch.delenv("ORCHEO_CHATKIT_STORAGE_PATH", raising=False)
    get_settings(refresh=True)


@pytest.mark.asyncio
async def test_chatkit_upload_enforces_size_limit(
    api_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uploads larger than the configured limit should be rejected."""

    storage_dir = tmp_path / "uploads"
    server = _RecordingServer()

    monkeypatch.setattr(
        backend_app.routers.chatkit, "_resolve_chatkit_server", lambda: server
    )
    monkeypatch.setenv("ORCHEO_CHATKIT_STORAGE_PATH", str(storage_dir))
    monkeypatch.setenv("ORCHEO_CHATKIT_MAX_UPLOAD_SIZE_BYTES", "4")
    get_settings(refresh=True)

    response = api_client.post(
        "/api/chatkit/upload",
        files={"file": ("note.txt", b"too big", "text/plain")},
    )

    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["code"] == "chatkit.upload.too_large"
    assert not storage_dir.exists()
    assert server.store.saved == []
    monkeypatch.delenv("ORCHEO_CHATKIT_STORAGE_PATH", raising=False)
    monkeypatch.delenv("ORCHEO_CHATKIT_MAX_UPLOAD_SIZE_BYTES", raising=False)
    get_settings(refresh=True)
