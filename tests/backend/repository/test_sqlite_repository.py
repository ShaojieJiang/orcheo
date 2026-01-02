from __future__ import annotations
import asyncio
import pathlib
from datetime import UTC, datetime
import aiosqlite
import pytest
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.manual import ManualDispatchItem, ManualDispatchRequest
from orcheo.triggers.retry import RetryPolicyConfig
from orcheo.triggers.webhook import WebhookTriggerConfig
from orcheo_backend.app.repository import (
    SqliteWorkflowRepository,
    WorkflowPublishStateError,
)
from orcheo_backend.app.repository_sqlite._base import (
    SqliteRepositoryBase,
    _parse_optional_datetime,
)


@pytest.mark.asyncio()
async def test_sqlite_repository_hydrates_failed_run_retry_state(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Failed runs maintain retry state after the SQLite repo restarts."""

    db_path = tmp_path_factory.mktemp("repo") / "workflow.sqlite"
    repository = SqliteWorkflowRepository(db_path)
    restart_repository: SqliteWorkflowRepository | None = None

    try:
        workflow = await repository.create_workflow(
            name="Retryable",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )
        await repository.create_version(
            workflow.id,
            graph={},
            metadata={},
            notes=None,
            created_by="author",
        )
        await repository.configure_retry_policy(
            workflow.id,
            RetryPolicyConfig(
                max_attempts=2,
                initial_delay_seconds=1.0,
                jitter_factor=0.0,
            ),
        )
        await repository.configure_webhook_trigger(
            workflow.id,
            WebhookTriggerConfig(allowed_methods={"POST"}),
        )
        await repository.configure_cron_trigger(
            workflow.id,
            CronTriggerConfig(expression="0 9 * * *", timezone="UTC"),
        )

        (cron_run,) = await repository.dispatch_due_cron_runs(
            now=datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
        )

        (run,) = await repository.dispatch_manual_runs(
            ManualDispatchRequest(
                workflow_id=workflow.id,
                actor="tester",
                runs=[ManualDispatchItem()],
            )
        )
        await repository.mark_run_failed(run.id, actor="worker", error="boom")

        restart_repository = SqliteWorkflowRepository(db_path)
        decision = await restart_repository.schedule_retry_for_run(run.id)
        assert decision is not None
        assert decision.retry_number == 1
        webhook_config = await restart_repository.get_webhook_trigger_config(
            workflow.id
        )
        assert "POST" in webhook_config.allowed_methods
        cron_config = await restart_repository.get_cron_trigger_config(workflow.id)
        assert cron_config.expression == "0 9 * * *"
        assert cron_run.id in restart_repository._trigger_layer._cron_run_index  # noqa: SLF001
    finally:
        if restart_repository is not None:
            await restart_repository.reset()
        await repository.reset()


def test_parse_optional_datetime_adds_utc_timezone() -> None:
    """Naive timestamps returned from SQLite should be converted to UTC."""

    iso_naive = "2025-01-01T00:00:00"
    parsed = _parse_optional_datetime(iso_naive)
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.isoformat().endswith("+00:00")


@pytest.mark.asyncio()
async def test_sqlite_ensure_cron_schema_migrations_adds_missing_column(
    tmp_path: pathlib.Path,
) -> None:
    """The migration adds the `last_dispatched_at` column when absent."""

    db_path = tmp_path / "legacy.sqlite"
    repo_base = SqliteRepositoryBase(db_path)

    async with aiosqlite.connect(str(db_path)) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(
            """
            CREATE TABLE cron_triggers (
                workflow_id TEXT PRIMARY KEY,
                config TEXT NOT NULL
            );
            """
        )
        await conn.commit()
        await repo_base._ensure_cron_schema_migrations(conn)
        cursor = await conn.execute("PRAGMA table_info(cron_triggers)")
        rows = await cursor.fetchall()

    assert any(row["name"] == "last_dispatched_at" for row in rows)


@pytest.mark.asyncio()
async def test_sqlite_dispatch_due_cron_runs_persists_last_dispatched(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Cron dispatch stores the latest dispatch time for recovery."""

    db_path = tmp_path_factory.mktemp("cron") / "dispatch.sqlite"
    repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await repository.create_workflow(
            name="Persistence Flow",
            slug=None,
            description=None,
            tags=None,
            actor="owner",
        )
        await repository.create_version(
            workflow.id,
            graph={},
            metadata={},
            notes=None,
            created_by="owner",
        )
        await repository.configure_cron_trigger(
            workflow.id,
            CronTriggerConfig(expression="0 9 * * *", timezone="UTC"),
        )

        now = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
        runs = await repository.dispatch_due_cron_runs(now=now)
        assert runs

        async with repository._connection() as conn:
            cursor = await conn.execute(
                "SELECT last_dispatched_at FROM cron_triggers WHERE workflow_id = ?",
                (str(workflow.id),),
            )
            row = await cursor.fetchone()

        assert row is not None
        assert row["last_dispatched_at"] == now.isoformat()
    finally:
        await repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_cron_dispatch_reflects_external_unschedule(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Cron dispatch refreshes configs when another process unschedules."""
    db_path = tmp_path_factory.mktemp("repo") / "workflow.sqlite"
    api_repository = SqliteWorkflowRepository(db_path)
    worker_repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await api_repository.create_workflow(
            name="Scheduled",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )
        await api_repository.create_version(
            workflow.id,
            graph={},
            metadata={},
            notes=None,
            created_by="author",
        )
        await api_repository.configure_cron_trigger(
            workflow.id,
            CronTriggerConfig(expression="* * * * *", timezone="UTC"),
        )

        first_runs = await worker_repository.dispatch_due_cron_runs(
            now=datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
        )
        assert len(first_runs) == 1

        await api_repository.delete_cron_trigger(workflow.id)

        follow_up = await worker_repository.dispatch_due_cron_runs(
            now=datetime(2025, 1, 1, 9, 1, tzinfo=UTC)
        )
        assert follow_up == []
    finally:
        await worker_repository.reset()
        await api_repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_refresh_cron_triggers_hydrates_missing_state(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Refresh loads cron configs that were added by other processes."""

    db_path = tmp_path_factory.mktemp("repo") / "refresh.sqlite"
    api_repository = SqliteWorkflowRepository(db_path)
    worker_repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await api_repository.create_workflow(
            name="Refresh Cron",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )
        await api_repository.configure_cron_trigger(
            workflow.id,
            CronTriggerConfig(expression="0 0 * * *", timezone="UTC"),
        )

        assert workflow.id not in worker_repository._trigger_layer._cron_states

        await worker_repository._refresh_cron_triggers()
        assert workflow.id in worker_repository._trigger_layer._cron_states
        assert (
            worker_repository._trigger_layer._cron_states[workflow.id].config.expression
            == "0 0 * * *"
        )
    finally:
        await worker_repository.reset()
        await api_repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_refresh_cron_triggers_updates_changed_configs(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Refreshing cron configs updates state when the persisted config changes."""

    db_path = tmp_path_factory.mktemp("repo") / "refresh-change.sqlite"
    primary_repository = SqliteWorkflowRepository(db_path)
    api_repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await primary_repository.create_workflow(
            name="Refresh Change",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )
        await primary_repository.create_version(
            workflow.id,
            graph={},
            metadata={},
            notes=None,
            created_by="author",
        )

        await primary_repository.configure_cron_trigger(
            workflow.id,
            CronTriggerConfig(expression="0 0 * * *", timezone="UTC"),
        )

        await api_repository.configure_cron_trigger(
            workflow.id,
            CronTriggerConfig(expression="0 0 * * *", timezone="America/Los_Angeles"),
        )

        await primary_repository._refresh_cron_triggers()
        updated_state = primary_repository._trigger_layer._cron_states[workflow.id]
        assert updated_state.config.timezone == "America/Los_Angeles"
    finally:
        await primary_repository.reset()
        await api_repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_refresh_cron_triggers_updates_last_dispatched_at(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Refreshing cron configs updates last_dispatched_at when it changes."""

    db_path = tmp_path_factory.mktemp("repo") / "refresh-last-dispatched.sqlite"
    worker_repository = SqliteWorkflowRepository(db_path)
    api_repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await api_repository.create_workflow(
            name="Refresh Dispatch Cursor",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )
        await api_repository.create_version(
            workflow.id,
            graph={},
            metadata={},
            notes=None,
            created_by="author",
        )
        await api_repository.configure_cron_trigger(
            workflow.id,
            CronTriggerConfig(expression="0 0 * * *", timezone="UTC"),
        )

        await worker_repository._refresh_cron_triggers()
        state = worker_repository._trigger_layer._cron_states[workflow.id]
        assert state.last_dispatched_at is None

        last_dispatched_at = datetime(2025, 1, 1, 9, 0, tzinfo=UTC)
        async with api_repository._connection() as conn:
            await conn.execute(
                """
                UPDATE cron_triggers
                   SET last_dispatched_at = ?
                 WHERE workflow_id = ?
                """,
                (last_dispatched_at.isoformat(), str(workflow.id)),
            )

        await worker_repository._refresh_cron_triggers()
        updated_state = worker_repository._trigger_layer._cron_states[workflow.id]
        assert updated_state.last_dispatched_at == last_dispatched_at
    finally:
        await worker_repository.reset()
        await api_repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_handle_webhook_trigger_success(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Webhook triggers enqueue runs with normalized payloads."""

    db_path = tmp_path_factory.mktemp("repo") / "webhook.sqlite"
    repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await repository.create_workflow(
            name="Webhook Flow",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )
        await repository.create_version(
            workflow.id,
            graph={},
            metadata={},
            notes=None,
            created_by="author",
        )
        await repository.configure_webhook_trigger(
            workflow.id, WebhookTriggerConfig(allowed_methods={"POST"})
        )

        run = await repository.handle_webhook_trigger(
            workflow.id,
            method="POST",
            headers={"X-Test": "value"},
            query_params={"ok": "1"},
            payload={"payload": True},
            source_ip="127.0.0.1",
        )

        assert run.triggered_by == "webhook"
        stored = await repository.get_run(run.id)
        assert stored.input_payload["body"] == {"payload": True}
        assert stored.input_payload["query_params"] == {"ok": "1"}
    finally:
        await repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_ensure_initialized_concurrent_calls(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Concurrent initialization requests exit early once setup completes."""

    db_path = tmp_path_factory.mktemp("repo") / "init.sqlite"
    repository = SqliteWorkflowRepository(db_path)

    try:
        await asyncio.gather(
            repository._ensure_initialized(),  # noqa: SLF001
            repository._ensure_initialized(),  # noqa: SLF001
        )
        assert repository._initialized is True  # noqa: SLF001
    finally:
        await repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_publish_revoke_workflow_lifecycle(
    tmp_path: pathlib.Path,
) -> None:
    """publish/revoke roundtrip persists workflow state."""

    db_path = tmp_path / "publish.sqlite"
    repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await repository.create_workflow(
            name="Lifecycle",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )
        published = await repository.publish_workflow(
            workflow.id,
            require_login=True,
            actor="author",
        )
        assert published.is_public is True
        assert published.require_login is True
        stored = await repository.get_workflow(workflow.id)
        assert stored.is_public is True

        revoked = await repository.revoke_publish(workflow.id, actor="auditor")
        assert revoked.is_public is False
    finally:
        await repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_publish_workflow_translates_value_error(
    tmp_path: pathlib.Path,
) -> None:
    """Publishing an already public workflow reports WorkflowPublishStateError."""

    db_path = tmp_path / "publish-conflict.sqlite"
    repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await repository.create_workflow(
            name="Conflict",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )
        await repository.publish_workflow(
            workflow.id,
            require_login=False,
            actor="author",
        )

        with pytest.raises(WorkflowPublishStateError):
            await repository.publish_workflow(
                workflow.id,
                require_login=False,
                actor="author",
            )
    finally:
        await repository.reset()


@pytest.mark.asyncio()
async def test_sqlite_revoke_requires_published_state(
    tmp_path: pathlib.Path,
) -> None:
    """Revoke propagates WorkflowPublishStateError when unpublished."""

    db_path = tmp_path / "publish-invalid.sqlite"
    repository = SqliteWorkflowRepository(db_path)

    try:
        workflow = await repository.create_workflow(
            name="Rotate Revoke",
            slug=None,
            description=None,
            tags=None,
            actor="author",
        )

        with pytest.raises(WorkflowPublishStateError):
            await repository.revoke_publish(workflow.id, actor="author")
    finally:
        await repository.reset()
