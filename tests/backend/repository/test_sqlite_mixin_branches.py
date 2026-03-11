"""Tests for branch coverage in SQLite repository mixins.

Covers:
  - _versions.py line 79->90: create_version skips listener sync when repo
    is not a ListenerRepositoryMixin.
  - _workflows.py line 37: _maybe_disable_listener_subscriptions returns early
    when should_disable=False.
  - _workflows.py line 43->exit: isawaitable(result) is False when
    _disable_listener_subscriptions_locked is synchronous.
"""

from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
import pytest
from orcheo_backend.app.repository_sqlite import SqliteWorkflowRepository
from orcheo_backend.app.repository_sqlite._versions import WorkflowVersionMixin
from orcheo_backend.app.repository_sqlite._workflows import WorkflowRepositoryMixin


class _VersionOnlyRepo(WorkflowRepositoryMixin, WorkflowVersionMixin):
    """Minimal SQLite repo that has no ListenerRepositoryMixin."""


class _WorkflowRepoNoDisable(WorkflowRepositoryMixin):
    """Workflow mixin stub that deliberately omits a disable-listener hook."""

    def __init__(self) -> None:
        """Skip SQLite base initialization for pure helper-method tests."""


@pytest.mark.asyncio
async def test_create_version_without_listener_mixin_skips_subscription_sync(
    tmp_path: Path,
) -> None:
    """create_version takes the 79->90 False branch when not ListenerRepositoryMixin."""
    with patch(
        "orcheo_backend.app.repository_sqlite._triggers._enqueue_run_for_execution"
    ):
        repo = _VersionOnlyRepo(tmp_path / "no_listener.sqlite")
        workflow = await repo.create_workflow(
            name="No Listener",
            slug=None,
            description=None,
            tags=None,
            actor="tester",
        )
        version = await repo.create_version(
            workflow.id,
            graph={"nodes": [], "edges": []},
            metadata={},
            notes=None,
            created_by="tester",
        )
    assert version.version == 1
    assert version.workflow_id == workflow.id


@pytest.mark.asyncio
async def test_update_workflow_name_only_hits_early_return(
    tmp_path: Path,
) -> None:
    """Name-only update calls
    _maybe_disable_listener_subscriptions(should_disable=False).

    This covers line 37: ``if not should_disable: return``.
    """
    with patch(
        "orcheo_backend.app.repository_sqlite._triggers._enqueue_run_for_execution"
    ):
        repo = SqliteWorkflowRepository(tmp_path / "name_update.sqlite")
        workflow = await repo.create_workflow(
            name="Original",
            slug=None,
            description=None,
            tags=None,
            actor="tester",
        )
        updated = await repo.update_workflow(
            workflow.id,
            name="Renamed",
            handle=None,
            description=None,
            tags=None,
            is_archived=None,
            actor="tester",
        )
    assert updated.name == "Renamed"


@pytest.mark.asyncio
async def test_maybe_disable_listener_subscriptions_returns_when_hook_missing() -> None:
    """_maybe_disable_listener_subscriptions exits when no disable hook exists."""
    repo = _WorkflowRepoNoDisable()

    await repo._maybe_disable_listener_subscriptions(  # noqa: SLF001
        uuid4(),
        should_disable=True,
        actor="tester",
        conn=object(),
    )


@pytest.mark.asyncio
async def test_archive_workflow_with_sync_disable_hook_covers_non_awaitable_branch(
    tmp_path: Path,
) -> None:
    """Covers line 43->exit: isawaitable(result) is False for a sync disable hook."""
    with patch(
        "orcheo_backend.app.repository_sqlite._triggers._enqueue_run_for_execution"
    ):
        repo = SqliteWorkflowRepository(tmp_path / "sync_hook.sqlite")
        workflow = await repo.create_workflow(
            name="Test",
            slug=None,
            description=None,
            tags=None,
            actor="tester",
        )

        called: list[object] = []

        def _sync_disable(workflow_id: object, *, actor: str, conn: object) -> None:
            called.append(workflow_id)

        # Replace the async method with a sync callable on the instance so that
        # isawaitable(result) evaluates to False in
        # _maybe_disable_listener_subscriptions.
        repo._disable_listener_subscriptions_locked = _sync_disable  # type: ignore[method-assign]

        archived = await repo.archive_workflow(workflow.id, actor="tester")

    assert archived.is_archived
    assert workflow.id in called
