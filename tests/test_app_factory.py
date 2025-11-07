"""Tests covering repository and FastAPI app factory helpers."""

import importlib
import pytest
from orcheo_backend.app import _create_repository, create_app, get_repository
from orcheo_backend.app.repository import InMemoryWorkflowRepository


backend_module = importlib.import_module("orcheo_backend.app")


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
        repository_backend = "postgres"
        repository_sqlite_path = "ignored.sqlite"

    monkeypatch.setattr(backend_module, "get_settings", lambda: DummySettings())

    with pytest.raises(ValueError, match="Unsupported repository backend"):
        _create_repository()
