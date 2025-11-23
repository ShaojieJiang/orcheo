"""Fixtures for backend API end-to-end tests."""

from __future__ import annotations
from collections.abc import Iterator
from importlib import import_module
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from orcheo.models import AesGcmCredentialCipher
from orcheo.vault import InMemoryCredentialVault
from orcheo.vault.oauth import OAuthCredentialService
from orcheo_backend.app import create_app
from orcheo_backend.app.authentication import reset_authentication_state
from orcheo_backend.app.chatkit_tokens import reset_chatkit_token_state
from orcheo_backend.app.repository import InMemoryWorkflowRepository


@pytest.fixture()
def api_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Yield a configured API client backed by a fresh repository."""

    monkeypatch.setenv("ORCHEO_AUTH_MODE", "disabled")
    monkeypatch.delenv("ORCHEO_AUTH_SERVICE_TOKENS", raising=False)
    monkeypatch.delenv("CHATKIT_TOKEN_SIGNING_KEY", raising=False)
    monkeypatch.delenv("ORCHEO_CHATKIT_TOKEN_SIGNING_KEY", raising=False)
    reset_authentication_state()
    reset_chatkit_token_state()

    factory_module = import_module("orcheo_backend.app.factory")
    monkeypatch.setattr(
        factory_module,
        "get_chatkit_server",
        lambda: object(),
    )
    monkeypatch.setattr(
        factory_module,
        "ensure_chatkit_cleanup_task",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        factory_module,
        "cancel_chatkit_cleanup_task",
        AsyncMock(return_value=None),
    )

    cipher = AesGcmCredentialCipher(key="api-client-key")
    vault = InMemoryCredentialVault(cipher=cipher)
    service = OAuthCredentialService(vault, token_ttl_seconds=600, providers={})
    repository = InMemoryWorkflowRepository(credential_service=service)
    app = create_app(repository, credential_service=service)
    app.state.vault = vault
    app.state.credential_service = service

    with TestClient(app) as client:
        yield client
