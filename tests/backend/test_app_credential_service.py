"""Tests for credential service initialization helpers."""

from __future__ import annotations
from types import SimpleNamespace
import pytest
from orcheo.vault import InMemoryCredentialVault
from orcheo_backend.app import (
    _credential_service_ref,
    _ensure_credential_service,
    _vault_ref,
    create_app,
    get_credential_service,
)


def test_ensure_credential_service_initializes_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Credential services are created once and cached for subsequent calls."""

    settings = SimpleNamespace(vault=SimpleNamespace(backend="inmemory"))

    monkeypatch.setitem(_vault_ref, "vault", None)
    monkeypatch.setitem(_credential_service_ref, "service", None)

    first = _ensure_credential_service(settings)  # type: ignore[arg-type]
    second = _ensure_credential_service(settings)  # type: ignore[arg-type]

    assert first is second
    assert _vault_ref["vault"] is not None


def test_ensure_credential_service_returns_existing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    monkeypatch.setitem(_credential_service_ref, "service", sentinel)

    service = _ensure_credential_service(SimpleNamespace())  # type: ignore[arg-type]

    assert service is sentinel


def test_ensure_credential_service_reuses_existing_vault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = InMemoryCredentialVault()
    monkeypatch.setitem(_vault_ref, "vault", vault)
    monkeypatch.setitem(_credential_service_ref, "service", None)

    service = _ensure_credential_service(SimpleNamespace())  # type: ignore[arg-type]

    assert service is not None
    assert _vault_ref["vault"] is vault


def test_create_app_infers_credential_service(monkeypatch: pytest.MonkeyPatch) -> None:
    class CredentialService:
        pass

    class Repository:
        _credential_service = CredentialService()

    monkeypatch.setitem(_credential_service_ref, "service", None)
    app = create_app(Repository())
    resolver = app.dependency_overrides[get_credential_service]
    assert resolver() is Repository._credential_service
