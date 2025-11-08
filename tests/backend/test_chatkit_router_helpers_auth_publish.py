"""Publish token authentication tests for ChatKit router helper functions."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException, status
from orcheo.models.workflow import hash_publish_token
from orcheo_backend.app.repository import (
    InMemoryWorkflowRepository,
    WorkflowNotFoundError,
)
from orcheo_backend.app.routers import chatkit
from tests.backend.chatkit_router_helpers_support import (
    make_chatkit_request,
)


pytestmark = pytest.mark.usefixtures("reset_chatkit_limiters")


class _MissingWorkflowPublishRepo:
    async def get_workflow(self, workflow_id: UUID) -> None:  # type: ignore[override]
        raise WorkflowNotFoundError(str(workflow_id))


@pytest.mark.asyncio()
async def test_authenticate_publish_request_requires_token() -> None:
    request = make_chatkit_request()
    repository = InMemoryWorkflowRepository()
    workflow_id = uuid4()

    with pytest.raises(HTTPException) as excinfo:
        await chatkit._authenticate_publish_request(
            request=request,
            workflow_id=workflow_id,
            publish_token=None,
            now=datetime.now(tz=UTC),
            repository=repository,
        )
    assert excinfo.value.detail["code"] == "chatkit.auth.publish_token_missing"


@pytest.mark.asyncio()
async def test_authenticate_publish_request_missing_workflow() -> None:
    request = make_chatkit_request()
    workflow_id = uuid4()

    with pytest.raises(HTTPException) as excinfo:
        await chatkit._authenticate_publish_request(
            request=request,
            workflow_id=workflow_id,
            publish_token="token",
            now=datetime.now(tz=UTC),
            repository=_MissingWorkflowPublishRepo(),
        )
    assert excinfo.value.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio()
async def test_authenticate_publish_request_requires_published_state() -> None:
    request = make_chatkit_request()
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Publish",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    with pytest.raises(HTTPException) as excinfo:
        await chatkit._authenticate_publish_request(
            request=request,
            workflow_id=workflow.id,
            publish_token="token",
            now=datetime.now(tz=UTC),
            repository=repository,
        )
    assert excinfo.value.detail["code"] == "chatkit.auth.not_published"


@pytest.mark.asyncio()
async def test_authenticate_publish_request_validates_token() -> None:
    request = make_chatkit_request()
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Publish",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    valid_token = "secret"
    await repository.publish_workflow(
        workflow.id,
        publish_token_hash=hash_publish_token(valid_token),
        require_login=False,
        actor="tester",
    )

    with pytest.raises(HTTPException) as excinfo:
        await chatkit._authenticate_publish_request(
            request=request,
            workflow_id=workflow.id,
            publish_token="invalid",
            now=datetime.now(tz=UTC),
            repository=repository,
        )
    assert excinfo.value.detail["code"] == "chatkit.auth.invalid_publish_token"
