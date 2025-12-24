"""Core behavior tests for the PostgreSQL-backed workflow repository.

These tests use in-memory fakes to verify repository behavior without requiring
a real PostgreSQL database connection.
"""

from __future__ import annotations
import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4
import pytest
from orcheo.models.workflow import WorkflowRunStatus
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.retry import RetryDecision, RetryPolicyConfig
from orcheo.triggers.webhook import WebhookTriggerConfig
from orcheo_backend.app.repository.errors import WorkflowPublishStateError
from orcheo_backend.app.repository_postgres import PostgresWorkflowRepository
from orcheo_backend.app.repository_postgres import _base as pg_base


class FakeRow(dict[str, Any]):
    """Fake row that supports both index and key access like psycopg rows."""

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class FakeCursor:
    """Fake database cursor for testing."""

    def __init__(
        self, *, row: dict[str, Any] | None = None, rows: list[Any] | None = None
    ) -> None:
        self._row = FakeRow(row) if row else None
        self._rows = [FakeRow(r) if isinstance(r, dict) else r for r in (rows or [])]

    async def fetchone(self) -> FakeRow | None:
        return self._row

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


class FakeConnection:
    """Fake database connection recording queries and returning configured responses."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.queries: list[tuple[str, Any | None]] = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, query: str, params: Any | None = None) -> FakeCursor:
        self.queries.append((query.strip(), params))
        response = self._responses.pop(0) if self._responses else {}
        if isinstance(response, FakeCursor):
            return response
        if isinstance(response, dict):
            return FakeCursor(row=response.get("row"), rows=response.get("rows"))
        if isinstance(response, list):
            return FakeCursor(rows=response)
        return FakeCursor()

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def __aenter__(self) -> FakeConnection:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        return None


class FakePool:
    """Fake connection pool that returns a pre-configured connection."""

    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    def connection(self) -> FakeConnection:
        return self._connection


def make_repository(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[Any],
    *,
    initialized: bool = True,
) -> PostgresWorkflowRepository:
    """Create a PostgresWorkflowRepository with fake connection pool."""
    monkeypatch.setattr(pg_base, "AsyncConnectionPool", object())
    monkeypatch.setattr(pg_base, "DictRowFactory", object())
    repo = PostgresWorkflowRepository("postgresql://test")
    repo._pool = FakePool(FakeConnection(responses))
    repo._initialized = initialized
    return repo


def _workflow_payload(workflow_id: UUID, **overrides: Any) -> dict[str, Any]:
    """Generate a fake workflow payload dictionary."""
    now = datetime.now(tz=UTC).isoformat()
    base = {
        "id": str(workflow_id),
        "name": "Test Workflow",
        "slug": "test-workflow",
        "description": None,
        "tags": [],
        "is_archived": False,
        "is_public": False,
        "published_at": None,
        "published_by": None,
        "require_login": False,
        "audit_log": [],
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


def _version_payload(
    version_id: UUID, workflow_id: UUID, version: int = 1, **overrides: Any
) -> dict[str, Any]:
    """Generate a fake version payload dictionary."""
    now = datetime.now(tz=UTC).isoformat()
    base = {
        "id": str(version_id),
        "workflow_id": str(workflow_id),
        "version": version,
        "graph": {},
        "metadata": {},
        "runnable_config": None,
        "notes": None,
        "created_by": "author",
        "audit_log": [],
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return base


def _run_payload(
    run_id: UUID,
    version_id: UUID,
    *,
    status: str = "pending",
    triggered_by: str = "manual",
    **overrides: Any,
) -> dict[str, Any]:
    """Generate a fake run payload dictionary."""
    now = datetime.now(tz=UTC).isoformat()
    base = {
        "id": str(run_id),
        "workflow_version_id": str(version_id),
        "status": status,
        "triggered_by": triggered_by,
        "input_payload": {},
        "runnable_config": {},
        "tags": [],
        "callbacks": [],
        "metadata": {},
        "run_name": None,
        "output_payload": None,
        "error": None,
        "audit_log": [],
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_postgres_repository_list_workflows_excludes_archived(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listing workflows excludes archived by default."""
    workflow_id_active = uuid4()
    workflow_id_archived = uuid4()

    responses: list[Any] = [
        {
            "rows": [
                {"payload": _workflow_payload(workflow_id_active)},
                {
                    "payload": _workflow_payload(
                        workflow_id_archived, is_archived=True, name="Archived"
                    )
                },
            ]
        },
    ]
    repo = make_repository(monkeypatch, responses)

    workflows = await repo.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].id == workflow_id_active


@pytest.mark.asyncio
async def test_postgres_repository_list_workflows_includes_archived(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listing workflows with include_archived=True returns all workflows."""
    workflow_id_active = uuid4()
    workflow_id_archived = uuid4()

    responses: list[Any] = [
        {
            "rows": [
                {"payload": _workflow_payload(workflow_id_active)},
                {
                    "payload": _workflow_payload(
                        workflow_id_archived, is_archived=True, name="Archived"
                    )
                },
            ]
        },
    ]
    repo = make_repository(monkeypatch, responses)

    workflows = await repo.list_workflows(include_archived=True)
    assert len(workflows) == 2


@pytest.mark.asyncio
async def test_postgres_repository_create_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creating a workflow persists it to the database."""
    responses: list[Any] = [{}]
    repo = make_repository(monkeypatch, responses)

    workflow = await repo.create_workflow(
        name="Test",
        slug="test-slug",
        description="Test description",
        tags=["tag1", "tag2"],
        actor="tester",
    )

    assert workflow.name == "Test"
    assert workflow.slug == "test-slug"
    assert workflow.description == "Test description"
    assert workflow.tags == ["tag1", "tag2"]
    assert workflow.audit_log[0].action == "workflow_created"


@pytest.mark.asyncio
async def test_postgres_repository_get_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Getting a workflow by ID returns the workflow."""
    workflow_id = uuid4()
    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id, name="Found")}},
    ]
    repo = make_repository(monkeypatch, responses)

    workflow = await repo.get_workflow(workflow_id)
    assert workflow.id == workflow_id
    assert workflow.name == "Found"


@pytest.mark.asyncio
async def test_postgres_repository_update_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Updating a workflow records changes and persists them."""
    workflow_id = uuid4()
    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id, name="Original")}},
        {},
    ]
    repo = make_repository(monkeypatch, responses)

    workflow = await repo.update_workflow(
        workflow_id,
        name="Updated",
        description="New description",
        tags=["new-tag"],
        is_archived=None,
        actor="updater",
    )

    assert workflow.name == "Updated"
    assert workflow.description == "New description"
    assert workflow.tags == ["new-tag"]
    assert any(e.action == "workflow_updated" for e in workflow.audit_log)


@pytest.mark.asyncio
async def test_postgres_repository_archive_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Archiving a workflow sets is_archived to True."""
    workflow_id = uuid4()
    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {},
    ]
    repo = make_repository(monkeypatch, responses)

    workflow = await repo.archive_workflow(workflow_id, actor="archiver")
    assert workflow.is_archived is True


@pytest.mark.asyncio
async def test_postgres_repository_publish_revoke_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Publishing and revoking workflows updates public state."""
    workflow_id = uuid4()

    # First call: get workflow for publish
    # Second call: update after publish
    # Third call: get workflow for revoke
    # Fourth call: update after revoke
    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {},
        {
            "row": {
                "payload": _workflow_payload(
                    workflow_id, is_public=True, require_login=True
                )
            }
        },
        {},
    ]
    repo = make_repository(monkeypatch, responses)

    published = await repo.publish_workflow(
        workflow_id, require_login=True, actor="publisher"
    )
    assert published.is_public is True
    assert published.require_login is True

    revoked = await repo.revoke_publish(workflow_id, actor="revoker")
    assert revoked.is_public is False


@pytest.mark.asyncio
async def test_postgres_repository_publish_already_public_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Publishing an already public workflow raises WorkflowPublishStateError."""
    workflow_id = uuid4()
    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id, is_public=True)}},
    ]
    repo = make_repository(monkeypatch, responses)

    with pytest.raises(WorkflowPublishStateError):
        await repo.publish_workflow(workflow_id, require_login=False, actor="publisher")


@pytest.mark.asyncio
async def test_postgres_repository_revoke_unpublished_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Revoking a non-public workflow raises WorkflowPublishStateError."""
    workflow_id = uuid4()
    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id, is_public=False)}},
    ]
    repo = make_repository(monkeypatch, responses)

    with pytest.raises(WorkflowPublishStateError):
        await repo.revoke_publish(workflow_id, actor="revoker")


@pytest.mark.asyncio
async def test_postgres_repository_webhook_trigger_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuring and retrieving webhook triggers works correctly."""
    workflow_id = uuid4()

    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {},  # INSERT webhook_triggers
    ]
    repo = make_repository(monkeypatch, responses)

    config = await repo.configure_webhook_trigger(
        workflow_id, WebhookTriggerConfig(allowed_methods={"POST", "PUT"})
    )

    assert "POST" in config.allowed_methods
    assert "PUT" in config.allowed_methods


@pytest.mark.asyncio
async def test_postgres_repository_cron_trigger_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuring and retrieving cron triggers works correctly."""
    workflow_id = uuid4()

    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {},  # INSERT cron_triggers
    ]
    repo = make_repository(monkeypatch, responses)

    config = await repo.configure_cron_trigger(
        workflow_id, CronTriggerConfig(expression="0 9 * * *", timezone="UTC")
    )

    assert config.expression == "0 9 * * *"
    assert config.timezone == "UTC"


@pytest.mark.asyncio
async def test_postgres_repository_retry_policy_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configuring and retrieving retry policies works correctly."""
    workflow_id = uuid4()

    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {},  # INSERT retry_policies
    ]
    repo = make_repository(monkeypatch, responses)

    config = await repo.configure_retry_policy(
        workflow_id,
        RetryPolicyConfig(max_attempts=3, initial_delay_seconds=1.0, jitter_factor=0.1),
    )

    assert config.max_attempts == 3


@pytest.mark.asyncio
async def test_postgres_repository_create_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Creating a version assigns an auto-incremented version number."""
    workflow_id = uuid4()

    responses: list[Any] = [
        # get_workflow for create_version
        {"row": {"payload": _workflow_payload(workflow_id)}},
        # SELECT max version
        {"row": {"max_version": None}},
        # INSERT workflow_versions
        {},
    ]
    repo = make_repository(monkeypatch, responses)

    version = await repo.create_version(
        workflow_id,
        graph={"nodes": []},
        metadata={"key": "value"},
        notes="Initial version",
        created_by="author",
    )

    assert version.workflow_id == workflow_id
    assert version.version == 1
    assert version.graph == {"nodes": []}
    assert version.metadata == {"key": "value"}


@pytest.mark.asyncio
async def test_postgres_repository_list_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listing versions returns versions ordered by version number."""
    workflow_id = uuid4()
    version_id_1 = uuid4()
    version_id_2 = uuid4()

    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {
            "rows": [
                {"payload": _version_payload(version_id_1, workflow_id, version=1)},
                {"payload": _version_payload(version_id_2, workflow_id, version=2)},
            ]
        },
    ]
    repo = make_repository(monkeypatch, responses)

    versions = await repo.list_versions(workflow_id)

    assert len(versions) == 2
    assert versions[0].version == 1
    assert versions[1].version == 2


@pytest.mark.asyncio
async def test_postgres_repository_list_runs_for_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listing runs for a workflow returns runs ordered by creation time."""
    workflow_id = uuid4()
    version_id = uuid4()
    run_id_1 = uuid4()
    run_id_2 = uuid4()

    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {
            "rows": [
                {"payload": _run_payload(run_id_1, version_id)},
                {"payload": _run_payload(run_id_2, version_id)},
            ]
        },
    ]
    repo = make_repository(monkeypatch, responses)

    runs = await repo.list_runs_for_workflow(workflow_id)

    assert len(runs) == 2
    assert runs[0].id == run_id_1
    assert runs[1].id == run_id_2


@pytest.mark.asyncio
async def test_postgres_repository_run_lifecycle_transitions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run status transitions work correctly (started -> succeeded/failed)."""
    workflow_id = uuid4()
    version_id = uuid4()
    run_id = uuid4()

    # For mark_run_started: get run, update
    responses: list[Any] = [
        {
            "row": {
                "payload": _run_payload(run_id, version_id, status="pending"),
                "workflow_id": str(workflow_id),
                "triggered_by": "manual",
                "status": "pending",
            }
        },
        {},
    ]
    repo = make_repository(monkeypatch, responses)

    run = await repo.mark_run_started(run_id, actor="worker")
    assert run.status == WorkflowRunStatus.RUNNING


@pytest.mark.asyncio
async def test_postgres_repository_mark_run_succeeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Marking a run as succeeded sets status and output."""
    workflow_id = uuid4()
    version_id = uuid4()
    run_id = uuid4()

    responses: list[Any] = [
        {
            "row": {
                "payload": _run_payload(run_id, version_id, status="running"),
                "workflow_id": str(workflow_id),
                "triggered_by": "manual",
                "status": "running",
            }
        },
        {},
    ]
    repo = make_repository(monkeypatch, responses)

    run = await repo.mark_run_succeeded(
        run_id, actor="worker", output={"result": "done"}
    )
    assert run.status == WorkflowRunStatus.SUCCEEDED
    assert run.output_payload == {"result": "done"}


@pytest.mark.asyncio
async def test_postgres_repository_mark_run_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Marking a run as failed sets status and error."""
    workflow_id = uuid4()
    version_id = uuid4()
    run_id = uuid4()

    responses: list[Any] = [
        {
            "row": {
                "payload": _run_payload(run_id, version_id, status="running"),
                "workflow_id": str(workflow_id),
                "triggered_by": "manual",
                "status": "running",
            }
        },
        {},
    ]
    repo = make_repository(monkeypatch, responses)

    run = await repo.mark_run_failed(run_id, actor="worker", error="Something broke")
    assert run.status == WorkflowRunStatus.FAILED
    assert run.error == "Something broke"


@pytest.mark.asyncio
async def test_postgres_repository_mark_run_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Marking a run as cancelled sets status and reason."""
    workflow_id = uuid4()
    version_id = uuid4()
    run_id = uuid4()

    responses: list[Any] = [
        {
            "row": {
                "payload": _run_payload(run_id, version_id, status="pending"),
                "workflow_id": str(workflow_id),
                "triggered_by": "manual",
                "status": "pending",
            }
        },
        {},
    ]
    repo = make_repository(monkeypatch, responses)

    run = await repo.mark_run_cancelled(run_id, actor="user", reason="No longer needed")
    assert run.status == WorkflowRunStatus.CANCELLED


@pytest.mark.asyncio
async def test_postgres_repository_reset_clears_all_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reset clears all workflow data from the repository."""
    # Reset executes 6 DELETE statements
    responses: list[Any] = [{}, {}, {}, {}, {}, {}]
    repo = make_repository(monkeypatch, responses)

    await repo.reset()

    # Verify trigger layer was reset
    assert len(repo._trigger_layer._cron_states) == 0
    assert len(repo._trigger_layer._webhook_states) == 0
    assert len(repo._trigger_layer._retry_configs) == 0


@pytest.mark.asyncio
async def test_postgres_repository_schedule_retry_for_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduling a retry for a failed run returns a retry decision."""
    workflow_id = uuid4()
    version_id = uuid4()
    run_id = uuid4()

    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {},  # INSERT retry_policies
        {
            "row": {
                "payload": _run_payload(run_id, version_id, status="failed"),
                "workflow_id": str(workflow_id),
                "triggered_by": "manual",
                "status": "failed",
            }
        },
    ]
    repo = make_repository(monkeypatch, responses)

    # Configure retry policy first
    await repo.configure_retry_policy(
        workflow_id,
        RetryPolicyConfig(max_attempts=3, initial_delay_seconds=1.0, jitter_factor=0.0),
    )

    # Track the run so retry can find its workflow
    repo._trigger_layer.track_run(workflow_id, run_id)

    # Schedule retry
    decision = await repo.schedule_retry_for_run(run_id)
    assert decision is not None
    assert isinstance(decision, RetryDecision)
    assert decision.retry_number == 1


@pytest.mark.asyncio
async def test_postgres_repository_ensure_initialized_runs_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Initialization only runs once even with concurrent calls."""
    repo = make_repository(monkeypatch, [], initialized=True)

    await asyncio.gather(
        repo._ensure_initialized(),
        repo._ensure_initialized(),
    )

    assert repo._initialized is True


@pytest.mark.asyncio
async def test_postgres_repository_delete_cron_trigger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deleting a cron trigger removes it from the database and trigger layer."""
    workflow_id = uuid4()

    responses: list[Any] = [
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {},  # INSERT cron_triggers
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {},  # DELETE cron_triggers
    ]
    repo = make_repository(monkeypatch, responses)

    # Configure first
    await repo.configure_cron_trigger(
        workflow_id, CronTriggerConfig(expression="0 9 * * *", timezone="UTC")
    )

    # Delete
    await repo.delete_cron_trigger(workflow_id)

    # Verify trigger layer no longer has the config
    assert workflow_id not in repo._trigger_layer._cron_states


@pytest.mark.asyncio
async def test_postgres_repository_diff_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diffing versions returns a unified diff."""
    workflow_id = uuid4()
    version_id_1 = uuid4()
    version_id_2 = uuid4()

    responses: list[Any] = [
        # get_version_by_number for base_version
        # (calls get_workflow then fetches version)
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {
            "row": {
                "payload": _version_payload(
                    version_id_1, workflow_id, version=1, graph={"nodes": ["a"]}
                )
            }
        },
        # get_version_by_number for target_version
        # (calls get_workflow then fetches version)
        {"row": {"payload": _workflow_payload(workflow_id)}},
        {
            "row": {
                "payload": _version_payload(
                    version_id_2, workflow_id, version=2, graph={"nodes": ["a", "b"]}
                )
            }
        },
    ]
    repo = make_repository(monkeypatch, responses)

    diff_result = await repo.diff_versions(
        workflow_id, base_version=1, target_version=2
    )

    # Diff result contains the version numbers and a diff list
    assert diff_result.base_version == 1
    assert diff_result.target_version == 2
    # The diff list should contain changes
    assert len(diff_result.diff) > 0
