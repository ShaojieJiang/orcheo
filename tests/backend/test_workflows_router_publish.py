"""Additional coverage for workflows publish router helpers."""

from __future__ import annotations
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from orcheo.models.workflow import Workflow
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowPublishStateError,
)
from orcheo_backend.app.routers import workflows
from orcheo_backend.app.schemas import (
    WorkflowPublishRequest,
    WorkflowPublishRevokeRequest,
    WorkflowPublishRotateRequest,
)


class _MissingPublishRepo:
    async def publish_workflow(self, workflow_id: UUID, **kwargs: object) -> Workflow:
        raise WorkflowNotFoundError(str(workflow_id))


class _InvalidRotateRepo:
    async def rotate_publish_token(
        self, workflow_id: UUID, **kwargs: object
    ) -> Workflow:
        raise WorkflowPublishStateError("invalid")


class _MissingRotateRepo:
    async def rotate_publish_token(
        self, workflow_id: UUID, **kwargs: object
    ) -> Workflow:
        raise WorkflowNotFoundError(str(workflow_id))


class _InvalidRevokeRepo:
    async def revoke_publish(self, workflow_id: UUID, **kwargs: object) -> Workflow:
        raise WorkflowPublishStateError("invalid")


class _MissingRevokeRepo:
    async def revoke_publish(self, workflow_id: UUID, **kwargs: object) -> Workflow:
        raise WorkflowNotFoundError(str(workflow_id))


class _AuditWorkflowRepo:
    def __init__(self) -> None:
        self.workflow = Workflow(name="Audit")
        self.workflow.record_event(
            actor="tester",
            action="workflow_unpublished",
            metadata={"previous_token": "publish:***123"},
        )

    async def revoke_publish(self, workflow_id: UUID, **kwargs: object) -> Workflow:
        return self.workflow


class _EmptyAuditWorkflowRepo:
    def __init__(self) -> None:
        self.workflow = Workflow(name="NoAudit")

    async def revoke_publish(self, workflow_id: UUID, **kwargs: object) -> Workflow:
        return self.workflow


class _NoPreviousTokenRepo:
    def __init__(self) -> None:
        self.workflow = Workflow(name="NoPrev")
        self.workflow.record_event(
            actor="tester",
            action="workflow_unpublished",
            metadata={},
        )

    async def revoke_publish(self, workflow_id: UUID, **kwargs: object) -> Workflow:
        return self.workflow


def test_publish_response_sets_and_omits_message_based_on_token() -> None:
    workflow = Workflow(name="Responder")
    response_with_token = workflows._publish_response(workflow, token="secret")
    assert response_with_token.message

    response_without_token = workflows._publish_response(workflow, token=None)
    assert response_without_token.message is None


@pytest.mark.asyncio()
async def test_publish_workflow_raises_not_found() -> None:
    request = WorkflowPublishRequest(actor="alice", require_login=False)

    with pytest.raises(HTTPException) as excinfo:
        await workflows.publish_workflow(
            uuid4(),
            request,
            _MissingPublishRepo(),
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio()
async def test_rotate_publish_token_translates_state_errors() -> None:
    request = WorkflowPublishRotateRequest(actor="alice")

    with pytest.raises(HTTPException) as excinfo:
        await workflows.rotate_publish_token(
            uuid4(),
            request,
            _InvalidRotateRepo(),
        )

    assert excinfo.value.status_code == 409


@pytest.mark.asyncio()
async def test_rotate_publish_token_not_found() -> None:
    request = WorkflowPublishRotateRequest(actor="alice")

    with pytest.raises(HTTPException) as excinfo:
        await workflows.rotate_publish_token(
            uuid4(),
            request,
            _MissingRotateRepo(),
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio()
async def test_revoke_publish_translates_state_errors() -> None:
    request = WorkflowPublishRevokeRequest(actor="alice")

    with pytest.raises(HTTPException) as excinfo:
        await workflows.revoke_workflow_publish(
            uuid4(),
            request,
            _InvalidRevokeRepo(),
        )

    assert excinfo.value.status_code == 409


@pytest.mark.asyncio()
async def test_revoke_publish_not_found() -> None:
    request = WorkflowPublishRevokeRequest(actor="alice")

    with pytest.raises(HTTPException) as excinfo:
        await workflows.revoke_workflow_publish(
            uuid4(),
            request,
            _MissingRevokeRepo(),
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio()
async def test_revoke_publish_logs_previous_token_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = WorkflowPublishRevokeRequest(actor="alice")
    repo = _AuditWorkflowRepo()
    captured: dict[str, str] = {}

    def _capture(message: str, *, extra: dict[str, str]) -> None:
        captured.update(extra)

    monkeypatch.setattr(workflows.logger, "info", _capture)

    result = await workflows.revoke_workflow_publish(
        repo.workflow.id,
        request,
        repo,
    )

    assert result is repo.workflow
    assert repo.workflow.audit_log[-1].metadata["previous_token"] == "publish:***123"
    assert captured["previous_token"] == "publish:***123"


@pytest.mark.asyncio()
async def test_revoke_publish_without_audit_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = WorkflowPublishRevokeRequest(actor="alice")
    repo = _EmptyAuditWorkflowRepo()
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        workflows.logger,
        "info",
        lambda message, *, extra: captured.update(extra),
    )

    result = await workflows.revoke_workflow_publish(
        repo.workflow.id,
        request,
        repo,
    )

    assert result is repo.workflow
    assert captured["previous_token"] == "unknown"


@pytest.mark.asyncio()
async def test_revoke_publish_without_previous_token_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = WorkflowPublishRevokeRequest(actor="alice")
    repo = _NoPreviousTokenRepo()
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        workflows.logger,
        "info",
        lambda message, *, extra: captured.update(extra),
    )

    await workflows.revoke_workflow_publish(
        repo.workflow.id,
        request,
        repo,
    )

    assert captured["previous_token"] == "unknown"
