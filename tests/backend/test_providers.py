"""Tests for backend provider factories."""

from __future__ import annotations
from types import SimpleNamespace
from typing import Any
import pytest
from orcheo.vault import InMemoryCredentialVault
from orcheo_backend.app import providers


class DummySettings:
    """Minimal Dynaconf-like stub using an internal mapping."""

    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def get(self, key: str, default: Any) -> Any:
        return self._values.get(key, default)


def test_settings_value_traverses_attr_path_when_get_missing() -> None:
    """settings_value should walk dotted attributes when get() is unavailable."""
    settings = SimpleNamespace(vault=SimpleNamespace(backend="inmemory"))

    result = providers.settings_value(
        settings,
        attr_path="vault.backend",
        env_key="VAULT_BACKEND",
        default="file",
    )

    assert result == "inmemory"


def test_settings_value_returns_default_when_attr_chain_missing() -> None:
    """settings_value should return default if the attr chain is incomplete."""
    settings = SimpleNamespace(vault={})

    result = providers.settings_value(
        settings,
        attr_path="vault.backend",
        env_key="VAULT_BACKEND",
        default="fallback",
    )

    assert result == "fallback"


def test_settings_value_without_attr_path_returns_default() -> None:
    """settings_value returns the default when attr_path is not provided."""
    settings = SimpleNamespace(vault=SimpleNamespace(backend="file"))

    result = providers.settings_value(
        settings,
        attr_path=None,
        env_key="VAULT_BACKEND",
        default="default-backend",
    )

    assert result == "default-backend"


def test_create_vault_inmemory_uses_provided_encryption_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_vault should honor the configured encryption key for inmemory backend."""

    settings = DummySettings(
        {
            "VAULT_BACKEND": "inmemory",
            "VAULT_ENCRYPTION_KEY": "override-key",
        }
    )

    captured: dict[str, str] = {}

    class FakeCipher:
        def __init__(self, *, key: str) -> None:
            captured["key"] = key

    monkeypatch.setattr(providers, "AesGcmCredentialCipher", FakeCipher)

    vault = providers.create_vault(settings)

    assert isinstance(vault, InMemoryCredentialVault)
    assert captured["key"] == "override-key"


def test_create_repository_sqlite_backend_sets_history_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_repository should configure sqlite repositories and history store."""
    settings = DummySettings(
        {
            "REPOSITORY_BACKEND": "sqlite",
            "REPOSITORY_SQLITE_PATH": "/tmp/workflows.sqlite",
        }
    )
    credential_service = object()
    history_store_ref: dict[str, object] = {}
    checkpoint_store_ref: dict[str, object] = {}

    class FakeStore:
        def __init__(self, path: str) -> None:
            self.path = path

    class FakeRepository:
        def __init__(self, path: str, *, credential_service: object) -> None:
            self.path = path
            self.credential_service = credential_service

    monkeypatch.setattr(providers, "SqliteRunHistoryStore", FakeStore)
    monkeypatch.setattr(providers, "SqliteAgentensorCheckpointStore", FakeStore)
    monkeypatch.setattr(providers, "SqliteWorkflowRepository", FakeRepository)

    repository = providers.create_repository(
        settings,
        credential_service=credential_service,
        history_store_ref=history_store_ref,
        checkpoint_store_ref=checkpoint_store_ref,
    )

    assert isinstance(repository, FakeRepository)
    assert repository.path == "/tmp/workflows.sqlite"
    assert repository.credential_service is credential_service
    assert isinstance(history_store_ref["store"], FakeStore)
    assert history_store_ref["store"].path == "/tmp/workflows.sqlite"
    assert isinstance(checkpoint_store_ref["store"], FakeStore)
    assert checkpoint_store_ref["store"].path == "/tmp/workflows.sqlite"
