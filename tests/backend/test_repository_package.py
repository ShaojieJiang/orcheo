"""Tests for repository package exports."""

from __future__ import annotations
import importlib
import pytest


def test_repository_module_exposes_sqlite_repository() -> None:
    """Accessing SqliteWorkflowRepository triggers the lazy import."""
    repository = importlib.import_module("orcheo_backend.app.repository")
    sqlite_module = importlib.import_module("orcheo_backend.app.repository_sqlite")

    assert repository.SqliteWorkflowRepository is sqlite_module.SqliteWorkflowRepository


def test_repository_module_rejects_unknown_attribute() -> None:
    """Unknown attributes should raise AttributeError via __getattr__."""
    repository = importlib.import_module("orcheo_backend.app.repository")

    with pytest.raises(AttributeError):
        repository.UnknownRepository  # noqa: B018
