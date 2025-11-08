from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.webhook import WebhookTriggerConfig
from orcheo_backend.app.repository import (
    InMemoryWorkflowRepository,
    WorkflowNotFoundError,
    WorkflowPublishStateError,
    WorkflowVersionNotFoundError,
)


@pytest.mark.asyncio()
async def test_inmemory_latest_version_missing_instance() -> None:
    """Missing latest version objects surface a dedicated error."""

    repository = InMemoryWorkflowRepository()

    workflow = await repository.create_workflow(
        name="Latest", slug=None, description=None, tags=None, actor="tester"
    )
    version = await repository.create_version(
        workflow.id,
        graph={},
        metadata={},
        notes=None,
        created_by="tester",
    )

    repository._versions.pop(version.id)  # noqa: SLF001

    with pytest.raises(WorkflowVersionNotFoundError):
        await repository.get_latest_version(workflow.id)


@pytest.mark.asyncio()
async def test_inmemory_handle_webhook_missing_version_object() -> None:
    """Webhook dispatch raises when the latest version is missing."""

    repository = InMemoryWorkflowRepository()

    workflow = await repository.create_workflow(
        name="Webhook", slug=None, description=None, tags=None, actor="tester"
    )
    version = await repository.create_version(
        workflow.id,
        graph={},
        metadata={},
        notes=None,
        created_by="tester",
    )
    await repository.configure_webhook_trigger(
        workflow.id, WebhookTriggerConfig(allowed_methods={"POST"})
    )

    repository._versions.pop(version.id)  # noqa: SLF001

    with pytest.raises(WorkflowVersionNotFoundError):
        await repository.handle_webhook_trigger(
            workflow.id,
            method="POST",
            headers={},
            query_params={},
            payload={},
            source_ip=None,
        )


@pytest.mark.asyncio()
async def test_inmemory_cron_dispatch_skips_missing_versions() -> None:
    """Cron dispatch ignores schedules when the latest version is missing."""

    repository = InMemoryWorkflowRepository()

    workflow = await repository.create_workflow(
        name="Cron", slug=None, description=None, tags=None, actor="owner"
    )
    version = await repository.create_version(
        workflow.id,
        graph={},
        metadata={},
        notes=None,
        created_by="owner",
    )
    await repository.configure_cron_trigger(
        workflow.id, CronTriggerConfig(expression="0 12 * * *", timezone="UTC")
    )

    repository._versions.pop(version.id)  # noqa: SLF001

    runs = await repository.dispatch_due_cron_runs(
        now=datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
    )
    assert runs == []


@pytest.mark.asyncio()
async def test_inmemory_publish_workflow_missing_id_raises_not_found() -> None:
    """publish_workflow raises WorkflowNotFoundError for unknown IDs."""

    repository = InMemoryWorkflowRepository()

    with pytest.raises(WorkflowNotFoundError):
        await repository.publish_workflow(
            uuid4(),
            publish_token_hash="hash",
            require_login=False,
            actor="tester",
        )


@pytest.mark.asyncio()
async def test_inmemory_publish_workflow_translates_value_errors() -> None:
    """ValueError from Workflow.publish is surfaced as WorkflowPublishStateError."""

    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Publish Twice", slug=None, description=None, tags=None, actor="tester"
    )
    await repository.publish_workflow(
        workflow.id,
        publish_token_hash="hash-1",
        require_login=False,
        actor="tester",
    )

    with pytest.raises(WorkflowPublishStateError):
        await repository.publish_workflow(
            workflow.id,
            publish_token_hash="hash-2",
            require_login=False,
            actor="tester",
        )


@pytest.mark.asyncio()
async def test_inmemory_rotate_publish_token_missing_workflow() -> None:
    """rotate_publish_token raises WorkflowNotFoundError for unknown workflows."""

    repository = InMemoryWorkflowRepository()

    with pytest.raises(WorkflowNotFoundError):
        await repository.rotate_publish_token(
            uuid4(),
            publish_token_hash="hash",
            actor="tester",
        )


@pytest.mark.asyncio()
async def test_inmemory_rotate_publish_token_requires_published_state() -> None:
    """rotate_publish_token translates invalid state errors."""

    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Rotate", slug=None, description=None, tags=None, actor="tester"
    )

    with pytest.raises(WorkflowPublishStateError):
        await repository.rotate_publish_token(
            workflow.id,
            publish_token_hash="hash",
            actor="tester",
        )


@pytest.mark.asyncio()
async def test_inmemory_revoke_publish_missing_workflow() -> None:
    """revoke_publish raises WorkflowNotFoundError for unknown workflows."""

    repository = InMemoryWorkflowRepository()

    with pytest.raises(WorkflowNotFoundError):
        await repository.revoke_publish(uuid4(), actor="tester")


@pytest.mark.asyncio()
async def test_inmemory_revoke_publish_requires_published_state() -> None:
    """revoke_publish also translates invalid state errors."""

    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Revoke",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    with pytest.raises(WorkflowPublishStateError):
        await repository.revoke_publish(workflow.id, actor="tester")
