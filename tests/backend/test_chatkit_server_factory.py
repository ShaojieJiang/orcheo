"""Tests for ChatKit FastAPI endpoint and server factory wiring."""

from __future__ import annotations
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from orcheo.vault import InMemoryCredentialVault
from orcheo_backend.app import app
from orcheo_backend.app.chatkit_service import create_chatkit_server
from orcheo_backend.app.repository import InMemoryWorkflowRepository


def test_chatkit_endpoint_rejects_invalid_payload() -> None:
    client = TestClient(app)
    response = client.post("/api/chatkit", content="{}")
    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["message"].startswith("Invalid ChatKit payload")


def test_create_chatkit_server_with_default_store() -> None:
    repository = InMemoryWorkflowRepository()

    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "test_chatkit.sqlite"

        mock_settings = MagicMock()
        mock_settings.get.return_value = str(sqlite_path)
        mock_settings.chatkit_sqlite_path = str(sqlite_path)

        with patch(
            "orcheo_backend.app.chatkit_service.get_settings",
            return_value=mock_settings,
        ):
            server = create_chatkit_server(repository, InMemoryCredentialVault)
            assert server is not None
            assert server._repository == repository


def test_create_chatkit_server_with_env_var() -> None:
    repository = InMemoryWorkflowRepository()

    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "env_chatkit.sqlite"

        mock_settings = MagicMock()
        mock_settings.get.return_value = str(sqlite_path)
        mock_settings.chatkit_sqlite_path = str(sqlite_path)

        with patch(
            "orcheo_backend.app.chatkit_service.get_settings",
            return_value=mock_settings,
        ):
            server = create_chatkit_server(repository, InMemoryCredentialVault)
            assert server is not None
