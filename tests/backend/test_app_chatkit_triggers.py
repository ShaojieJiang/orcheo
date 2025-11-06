"""Tests for ChatKit workflow trigger endpoint."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from orcheo.models import CredentialHealthStatus
from orcheo.models.workflow import WorkflowRun, WorkflowVersion
from orcheo.vault.oauth import (
    CredentialHealthError,
    CredentialHealthReport,
    CredentialHealthResult,
)
from orcheo_backend.app import trigger_chatkit_workflow
from orcheo_backend.app.repository import WorkflowNotFoundError
from orcheo_backend.app.schemas import ChatKitWorkflowTriggerRequest


def _health_error(workflow_id: UUID) -> CredentialHealthError:
    report = CredentialHealthReport(
        workflow_id=workflow_id,
        results=[
            CredentialHealthResult(
                credential_id=uuid4(),
                name="Slack",
                provider="slack",
                status=CredentialHealthStatus.UNHEALTHY,
                last_checked_at=datetime.now(tz=UTC),
                failure_reason="expired",
            )
        ],
        checked_at=datetime.now(tz=UTC),
    )
    return CredentialHealthError(report)


@pytest.mark.asyncio()
async def test_trigger_chatkit_workflow_creates_run() -> None:
    """ChatKit trigger creates a workflow run."""

    workflow_id = uuid4()
    run_id = uuid4()

    class Repository:
        async def get_latest_version(self, wf_id):
            return WorkflowVersion(
                id=uuid4(),
                workflow_id=wf_id,
                version=1,
                graph={},
                created_by="system",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=workflow_version_id,
                triggered_by=triggered_by,
                input_payload=input_payload,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = ChatKitWorkflowTriggerRequest(
        message="Hello",
        client_thread_id="thread-123",
        actor="user@example.com",
    )

    result = await trigger_chatkit_workflow(workflow_id, request, Repository())

    assert result.id == run_id
    assert result.triggered_by == "user@example.com"


@pytest.mark.asyncio()
async def test_trigger_chatkit_workflow_missing_workflow() -> None:
    """ChatKit trigger raises 404 for missing workflow."""

    workflow_id = uuid4()

    class Repository:
        async def get_latest_version(self, wf_id):
            raise WorkflowNotFoundError("not found")

    request = ChatKitWorkflowTriggerRequest(
        message="Hello",
        client_thread_id="thread-123",
        actor="user@example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        await trigger_chatkit_workflow(workflow_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_trigger_chatkit_workflow_credential_health_error() -> None:
    """ChatKit trigger handles credential health errors."""

    workflow_id = uuid4()

    class Repository:
        async def get_latest_version(self, wf_id):
            return WorkflowVersion(
                id=uuid4(),
                workflow_id=wf_id,
                version=1,
                graph={},
                created_by="system",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            raise _health_error(wf_id)

    request = ChatKitWorkflowTriggerRequest(
        message="Hello",
        client_thread_id="thread-123",
        actor="user@example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        await trigger_chatkit_workflow(workflow_id, request, Repository())

    assert exc_info.value.status_code == 422
