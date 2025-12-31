"""Coverage for the public workflow router endpoint."""

from __future__ import annotations
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from orcheo.models.workflow import Workflow
from orcheo_backend.app.repository import WorkflowNotFoundError
from orcheo_backend.app.routers import workflows


class _WorkflowRepo:
    def __init__(self, workflow: Workflow) -> None:
        self.workflow = workflow

    async def get_workflow(self, workflow_id: UUID) -> Workflow:
        if workflow_id != self.workflow.id:
            raise WorkflowNotFoundError(str(workflow_id))
        return self.workflow


class _MissingWorkflowRepo:
    async def get_workflow(self, workflow_id: UUID) -> Workflow:
        raise WorkflowNotFoundError(str(workflow_id))


@pytest.mark.asyncio()
async def test_get_public_workflow_not_found() -> None:
    with pytest.raises(HTTPException) as excinfo:
        await workflows.get_public_workflow(
            uuid4(),
            _MissingWorkflowRepo(),
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio()
async def test_get_public_workflow_denies_private_workflows() -> None:
    workflow = Workflow(name="Hidden workflow", is_public=False)
    repo = _WorkflowRepo(workflow)

    with pytest.raises(HTTPException) as excinfo:
        await workflows.get_public_workflow(workflow.id, repo)

    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "workflow.not_public"


@pytest.mark.asyncio()
async def test_get_public_workflow_includes_share_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow = Workflow(name="Published workflow", is_public=True)
    repo = _WorkflowRepo(workflow)
    monkeypatch.setattr(
        workflows,
        "_resolve_chatkit_public_base_url",
        lambda: "https://canvas.example",
    )

    response = await workflows.get_public_workflow(workflow.id, repo)

    assert response.share_url == f"https://canvas.example/chat/{workflow.id}"
