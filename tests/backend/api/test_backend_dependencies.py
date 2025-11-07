from __future__ import annotations
import importlib
import pytest
from orcheo_backend.app import dependencies


def test_create_vault_delegates_to_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_create_vault proxies to providers.create_vault with the same settings."""
    settings = object()
    captured: dict[str, object] = {}

    def fake_create_vault(settings_arg: object) -> str:
        captured["settings"] = settings_arg
        return "vault"

    monkeypatch.setattr(dependencies, "create_vault", fake_create_vault)

    result = dependencies._create_vault(settings)

    assert result == "vault"
    assert captured["settings"] is settings


def test_ensure_credential_service_without_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_ensure_credential_service loads settings when none provided."""
    sentinel_settings = object()
    sentinel_vault = object()
    sentinel_service = object()
    monkeypatch.setitem(dependencies._credential_service_ref, "service", None)
    app_module = importlib.import_module("orcheo_backend.app")
    monkeypatch.setattr(app_module, "get_settings", lambda: sentinel_settings)
    monkeypatch.setattr(dependencies, "_ensure_vault", lambda: sentinel_vault)

    called: dict[str, tuple[object, object]] = {}

    def fake_ensure(settings: object, vault: object) -> object:
        called["args"] = (settings, vault)
        return sentinel_service

    monkeypatch.setattr(
        dependencies,
        "ensure_credential_service",
        fake_ensure,
    )

    service = dependencies._ensure_credential_service()

    assert service is sentinel_service
    assert called["args"] == (sentinel_settings, sentinel_vault)
    assert dependencies._credential_service_ref["service"] is sentinel_service


def test_create_repository_uses_explicit_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_create_repository skips dynaconf lookup when settings provided."""
    sentinel_settings = object()
    sentinel_service = object()
    sentinel_repository = object()
    monkeypatch.setitem(dependencies._repository_ref, "repository", None)

    monkeypatch.setattr(
        dependencies,
        "_ensure_credential_service",
        lambda settings: sentinel_service,
    )

    captured: dict[str, tuple[object, object, object]] = {}

    def fake_create_repository(
        settings: object,
        credential_service: object,
        history_store_ref: object,
    ) -> object:
        captured["args"] = (settings, credential_service, history_store_ref)
        return sentinel_repository

    monkeypatch.setattr(
        dependencies,
        "create_repository",
        fake_create_repository,
    )

    repository = dependencies._create_repository(settings=sentinel_settings)

    assert repository is sentinel_repository
    assert captured["args"] == (
        sentinel_settings,
        sentinel_service,
        dependencies._history_store_ref,
    )
    assert dependencies._repository_ref["repository"] is sentinel_repository


def test_get_repository_initializes_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_get_repository bootstraps the singleton when empty."""
    sentinel_repository = object()
    monkeypatch.setitem(dependencies._repository_ref, "repository", None)
    monkeypatch.setattr(
        dependencies,
        "_create_repository",
        lambda: sentinel_repository,
    )

    repository = dependencies._get_repository()

    assert repository is sentinel_repository
