from __future__ import annotations
import hashlib
import json
import sqlite3
import tempfile
from datetime import UTC, datetime
from pathlib import Path
import jwt
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from orcheo_backend.app.authentication import (
    ServiceTokenRecord,
    reset_authentication_state,
)
from orcheo_backend.app.chatkit_tokens import reset_chatkit_token_state
from orcheo_backend.app.service_token_repository import SqliteServiceTokenRepository
from .shared import create_workflow_with_version


def _setup_service_token(
    monkeypatch: pytest.MonkeyPatch,
    token_secret: str,
    *,
    identifier: str | None = None,
    scopes: list[str] | None = None,
) -> None:
    """Set up a service token for testing."""

    temp_dir = tempfile.mkdtemp()
    db_path = str(Path(temp_dir) / "test_tokens.sqlite")
    monkeypatch.setenv("ORCHEO_AUTH_SERVICE_TOKEN_DB_PATH", db_path)

    _ = SqliteServiceTokenRepository(db_path)
    token_hash = hashlib.sha256(token_secret.encode("utf-8")).hexdigest()
    record = ServiceTokenRecord(
        identifier=identifier or "test-token",
        secret_hash=token_hash,
        scopes=frozenset(scopes or []),
        workspace_ids=frozenset(),
        issued_at=datetime.now(tz=UTC),
    )

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO service_tokens (
            identifier, secret_hash, scopes, workspace_ids,
            created_at, issued_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record.identifier,
            record.secret_hash,
            json.dumps(sorted(record.scopes)) if record.scopes else None,
            json.dumps(sorted(record.workspace_ids)) if record.workspace_ids else None,
            datetime.now(tz=UTC).isoformat(),
            record.issued_at.isoformat() if record.issued_at else None,
        ),
    )
    conn.commit()
    conn.close()


def test_chatkit_session_returns_configured_secret(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    """The ChatKit session endpoint issues a signed token with metadata."""

    _setup_service_token(
        monkeypatch, "session-token", identifier="cli", scopes=["chatkit:session"]
    )
    monkeypatch.setenv("CHATKIT_TOKEN_SIGNING_KEY", "api-signing-key")
    monkeypatch.setenv("ORCHEO_CHATKIT_TOKEN_SIGNING_KEY", "api-signing-key")
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    reset_authentication_state()
    reset_chatkit_token_state()

    response = api_client.post(
        "/api/chatkit/session",
        headers={"Authorization": "Bearer session-token"},
        json={"user": {"id": "tester"}, "assistant": {"id": "orcheo"}},
    )

    assert response.status_code == status.HTTP_200_OK
    token = response.json()["client_secret"]
    decoded = jwt.decode(
        token,
        "api-signing-key",
        algorithms=["HS256"],
        audience="chatkit",
        issuer="orcheo.chatkit",
    )
    assert decoded["chatkit"]["identity_type"] == "service"


def test_chatkit_session_prefers_workflow_specific_secret(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    """Workflow identifiers should be embedded within the signed token."""

    workflow_id, _ = create_workflow_with_version(api_client)
    _setup_service_token(
        monkeypatch, "session-token", identifier="cli", scopes=["chatkit:session"]
    )
    monkeypatch.setenv("CHATKIT_TOKEN_SIGNING_KEY", "api-signing-key")
    monkeypatch.setenv("ORCHEO_CHATKIT_TOKEN_SIGNING_KEY", "api-signing-key")
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    reset_authentication_state()
    reset_chatkit_token_state()

    response = api_client.post(
        "/api/chatkit/session",
        headers={"Authorization": "Bearer session-token"},
        json={"workflowId": workflow_id, "currentClientSecret": None},
    )

    assert response.status_code == status.HTTP_200_OK
    token = response.json()["client_secret"]
    decoded = jwt.decode(
        token,
        "api-signing-key",
        algorithms=["HS256"],
        audience="chatkit",
        issuer="orcheo.chatkit",
    )
    assert decoded["chatkit"]["workflow_id"] == workflow_id


def test_chatkit_session_missing_secret_returns_service_unavailable(
    monkeypatch: pytest.MonkeyPatch, api_client: TestClient
) -> None:
    """Missing ChatKit signing key surfaces a configuration error."""

    _setup_service_token(
        monkeypatch, "session-token", identifier="cli", scopes=["chatkit:session"]
    )
    monkeypatch.delenv("CHATKIT_TOKEN_SIGNING_KEY", raising=False)
    monkeypatch.delenv("ORCHEO_CHATKIT_TOKEN_SIGNING_KEY", raising=False)
    monkeypatch.setenv("ORCHEO_AUTH_MODE", "required")
    reset_authentication_state()
    reset_chatkit_token_state()

    response = api_client.post(
        "/api/chatkit/session",
        headers={"Authorization": "Bearer session-token"},
        json={},
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    detail = response.json()["detail"]
    assert "signing key" in detail["message"].lower()
