from __future__ import annotations
import asyncio
import pathlib
from datetime import UTC, datetime
import pytest
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.manual import ManualDispatchItem, ManualDispatchRequest
from orcheo.triggers.retry import RetryPolicyConfig
from orcheo.triggers.webhook import WebhookTriggerConfig
from orcheo_backend.app.repository import (
    SqliteWorkflowRepository,
    WorkflowPublishStateError,
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
