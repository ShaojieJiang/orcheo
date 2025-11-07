from __future__ import annotations
from datetime import UTC, datetime
import pytest
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.webhook import WebhookTriggerConfig
from orcheo_backend.app.repository import (
    InMemoryWorkflowRepository,
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
