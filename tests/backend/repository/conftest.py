"""Shared fixtures for workflow repository backend tests."""

from __future__ import annotations
from collections.abc import AsyncIterator, Generator
from pathlib import Path
from unittest.mock import patch
import pytest
import pytest_asyncio
from orcheo_backend.app.repository import (
    InMemoryWorkflowRepository,
    SqliteWorkflowRepository,
    WorkflowRepository,
)


@pytest.fixture(autouse=True)
def mock_celery_enqueue() -> Generator[None, None, None]:
    """Disable Celery enqueue for all repository tests to avoid Redis hangs."""
    with patch(
        "orcheo_backend.app.repository_sqlite._triggers._enqueue_run_for_execution"
    ):
        yield


@pytest_asyncio.fixture(params=["memory", "sqlite"])
async def repository(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> AsyncIterator[WorkflowRepository]:
    """Yield a repository instance backed by either the in-memory or SQLite backend."""

    if request.param == "memory":
        repo: WorkflowRepository = InMemoryWorkflowRepository()
    else:
        db_root = Path(tmp_path_factory.mktemp("repo"))
        repo = SqliteWorkflowRepository(db_root / "workflows.sqlite")

    try:
        yield repo
    finally:
        await repo.reset()
