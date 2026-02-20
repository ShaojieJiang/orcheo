"""Tests covering repository and FastAPI app factory helpers."""

import importlib
import json
import sys
from types import ModuleType
import pytest
from fastapi import Request
from orcheo_backend.app import _create_repository, create_app, get_repository
from orcheo_backend.app._app_module import _AppModule, install_app_module_proxy
from orcheo_backend.app.authentication import AuthenticationError
from orcheo_backend.app.factory import (
    _DEFAULT_ALLOWED_ORIGINS,
    _authentication_error_handler,
    _load_allowed_origins,
)
from orcheo_backend.app.repository import InMemoryWorkflowRepository


backend_module = importlib.import_module("orcheo_backend.app")


def test_install_app_module_proxy_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installing the proxy twice should be a no-op on the second call."""
    module_name = "tests.dummy_app_module"
    dummy_module = ModuleType(module_name)
    monkeypatch.setitem(sys.modules, module_name, dummy_module)

    install_app_module_proxy(module_name)
    proxied_module = sys.modules[module_name]
    assert isinstance(proxied_module, _AppModule)

    install_app_module_proxy(module_name)
    assert sys.modules[module_name] is proxied_module

    sys.modules.pop(module_name, None)


def test_app_module_exposes_sensitive_debug_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The module proxy forwards _should_log_sensitive_debug lookups."""
    sentinel = object()
    monkeypatch.setattr(
        backend_module._workflow_execution_module,  # type: ignore[attr-defined]
        "_should_log_sensitive_debug",
        sentinel,
        raising=False,
    )

    monkeypatch.delattr(backend_module, "_should_log_sensitive_debug", raising=False)

    assert backend_module._should_log_sensitive_debug is sentinel  # type: ignore[attr-defined]


def test_get_repository_returns_singleton() -> None:
    """The module-level repository accessor returns a singleton instance."""

    first = get_repository()
    second = get_repository()
    assert first is second


def test_create_app_allows_dependency_override() -> None:
    """Passing a repository instance wires it into FastAPI dependency overrides."""

    repository = InMemoryWorkflowRepository()
    app = create_app(repository)

    override = app.dependency_overrides[get_repository]
    assert override() is repository


def test_create_repository_inmemory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """The application factory instantiates the in-memory repository."""

    class DummySettings:
        repository_backend = "inmemory"
        repository_sqlite_path = "ignored.sqlite"

    monkeypatch.setattr(backend_module, "get_settings", lambda: DummySettings())

    repository = _create_repository()
    assert isinstance(repository, InMemoryWorkflowRepository)


def test_create_repository_invalid_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unsupported repository backends raise a clear error."""

    class DummySettings:
        repository_backend = "invalid_backend"
        repository_sqlite_path = "ignored.sqlite"

    monkeypatch.setattr(backend_module, "get_settings", lambda: DummySettings())

    with pytest.raises(ValueError, match="Unsupported repository backend"):
        _create_repository()


def test_load_allowed_origins_reads_json_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """JSON arrays should be parsed, trimmed, and filtered."""
    monkeypatch.setenv(
        "ORCHEO_CORS_ALLOW_ORIGINS",
        json.dumps([" https://foo.example ", ""]),
    )

    origins = _load_allowed_origins()
    assert origins == ["https://foo.example"]


def test_load_allowed_origins_reads_csv_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Comma-separated values fallback when JSON parsing fails."""
    monkeypatch.setenv(
        "ORCHEO_CORS_ALLOW_ORIGINS",
        "https://a.example, ,https://b.example  ",
    )

    origins = _load_allowed_origins()
    assert origins == ["https://a.example", "https://b.example"]


def test_load_allowed_origins_defaults_when_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the filtered list is empty the defaults should be returned."""
    monkeypatch.setenv(
        "ORCHEO_CORS_ALLOW_ORIGINS",
        json.dumps(["", "   "]),
    )

    origins = _load_allowed_origins()
    assert origins == list(_DEFAULT_ALLOWED_ORIGINS)
    assert origins is not _DEFAULT_ALLOWED_ORIGINS


def test_load_allowed_origins_defaults_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the env var is unset, the defaults should be returned."""
    monkeypatch.delenv("ORCHEO_CORS_ALLOW_ORIGINS", raising=False)

    origins = _load_allowed_origins()
    assert origins == list(_DEFAULT_ALLOWED_ORIGINS)
    assert origins is not _DEFAULT_ALLOWED_ORIGINS


@pytest.mark.asyncio
async def test_authentication_error_handler_maps_to_http_response() -> None:
    """Authentication errors should map to FastAPI's HTTP exception handler."""
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
    error = AuthenticationError("missing token")

    response = await _authentication_error_handler(request, error)

    assert response.status_code == 401
