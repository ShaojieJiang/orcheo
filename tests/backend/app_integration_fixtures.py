"""Shared fixtures for backend integration tests that hit the FastAPI app."""

from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from orcheo_backend.app import create_app
from orcheo_backend.app.history import InMemoryRunHistoryStore
from orcheo_backend.app.repository import InMemoryWorkflowRepository


@pytest.fixture
def repository() -> InMemoryWorkflowRepository:
    """Provide an in-memory workflow repository."""
    return InMemoryWorkflowRepository()


@pytest.fixture
def history_store() -> InMemoryRunHistoryStore:
    """Provide an in-memory run history store."""
    return InMemoryRunHistoryStore()


@pytest.fixture
def client(
    repository: InMemoryWorkflowRepository,
    history_store: InMemoryRunHistoryStore,
) -> TestClient:
    """Return a TestClient wired up with in-memory dependencies."""
    app = create_app(repository=repository, history_store=history_store)
    return TestClient(app)
