"""Tests for workflow run CRUD endpoints."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from orcheo.models import CredentialHealthStatus
from orcheo.models.workflow import WorkflowRun
from orcheo.vault.oauth import (
    CredentialHealthError,
    CredentialHealthReport,
    CredentialHealthResult,
)
from orcheo_backend.app import (
    create_workflow_run,
    get_workflow_run,
    list_workflow_runs,
)
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowRunNotFoundError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.schemas.workflows import WorkflowRunCreateRequest


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
async def test_create_workflow_run_success() -> None:
    """Create workflow run endpoint creates and returns new run."""

    workflow_id = uuid4()
    run_id = uuid4()
    version_id = uuid4()

    class Repository:
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

    request = WorkflowRunCreateRequest(
        workflow_version_id=version_id,
        triggered_by="user@example.com",
        input_payload={"key": "value"},
    )

    result = await create_workflow_run(workflow_id, request, Repository(), None)

    assert result.id == run_id
    assert result.triggered_by == "user@example.com"


@pytest.mark.asyncio()
async def test_create_workflow_run_workflow_not_found() -> None:
    """Create workflow run raises 404 for missing workflow."""

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            raise WorkflowNotFoundError("not found")

    request = WorkflowRunCreateRequest(
        workflow_version_id=version_id,
        triggered_by="user@example.com",
        input_payload={},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workflow_run(workflow_id, request, Repository(), None)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_create_workflow_run_version_not_found() -> None:
    """Create workflow run raises 404 for missing version."""

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            raise WorkflowVersionNotFoundError("not found")

    request = WorkflowRunCreateRequest(
        workflow_version_id=version_id,
        triggered_by="user@example.com",
        input_payload={},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workflow_run(workflow_id, request, Repository(), None)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_create_workflow_run_credential_health_error() -> None:
    """Create workflow run handles credential health errors."""

    workflow_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def create_run(
            self, wf_id, workflow_version_id, triggered_by, input_payload
        ):
            raise _health_error(wf_id)

    request = WorkflowRunCreateRequest(
        workflow_version_id=version_id,
        triggered_by="user@example.com",
        input_payload={},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_workflow_run(workflow_id, request, Repository(), None)

    assert exc_info.value.status_code == 422


@pytest.mark.asyncio()
async def test_list_workflow_runs_success() -> None:
    """List workflow runs endpoint returns runs."""

    workflow_id = uuid4()
    run1_id = uuid4()
    run2_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def list_runs_for_workflow(self, wf_id):
            return [
                WorkflowRun(
                    id=run1_id,
                    workflow_version_id=version_id,
                    triggered_by="user1",
                    input_payload={},
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
                WorkflowRun(
                    id=run2_id,
                    workflow_version_id=version_id,
                    triggered_by="user2",
                    input_payload={},
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
            ]

    result = await list_workflow_runs(workflow_id, Repository())

    assert len(result) == 2
    assert result[0].id == run1_id
    assert result[1].id == run2_id


@pytest.mark.asyncio()
async def test_list_workflow_runs_not_found() -> None:
    """List workflow runs raises 404 for missing workflow."""

    workflow_id = uuid4()

    class Repository:
        async def list_runs_for_workflow(self, wf_id):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await list_workflow_runs(workflow_id, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_get_workflow_run_success() -> None:
    """Get workflow run endpoint returns specific run."""

    run_id = uuid4()
    version_id = uuid4()

    class Repository:
        async def get_run(self, run_id):
            return WorkflowRun(
                id=run_id,
                workflow_version_id=version_id,
                triggered_by="user",
                input_payload={},
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = await get_workflow_run(run_id, Repository())

    assert result.id == run_id


@pytest.mark.asyncio()
async def test_get_workflow_run_not_found() -> None:
    """Get workflow run raises 404 for missing run."""

    run_id = uuid4()

    class Repository:
        async def get_run(self, run_id):
            raise WorkflowRunNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_run(run_id, Repository())

    assert exc_info.value.status_code == 404
