"""Tests for workflow CRUD endpoints in ``orcheo_backend.app``."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from orcheo.models.workflow import Workflow
from orcheo_backend.app import (
    archive_workflow,
    create_workflow,
    get_workflow,
    list_workflows,
    update_workflow,
)
from orcheo_backend.app.repository import WorkflowNotFoundError
from orcheo_backend.app.schemas import WorkflowCreateRequest, WorkflowUpdateRequest


@pytest.mark.asyncio()
async def test_list_workflows_returns_all() -> None:
    """List workflows endpoint returns all workflows."""
    workflow1 = Workflow(
        id=uuid4(),
        name="Workflow 1",
        slug="workflow-1",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    workflow2 = Workflow(
        id=uuid4(),
        name="Workflow 2",
        slug="workflow-2",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )

    class Repository:
        async def list_workflows(self, *, include_archived: bool = False):
            return [workflow1, workflow2]

    result = await list_workflows(Repository(), include_archived=False)

    assert len(result) == 2
    assert result[0].id == workflow1.id
    assert result[1].id == workflow2.id


@pytest.mark.asyncio()
async def test_create_workflow_returns_new_workflow() -> None:
    """Create workflow endpoint creates and returns new workflow."""
    workflow_id = uuid4()

    class Repository:
        async def create_workflow(self, name, slug, description, tags, actor):
            return Workflow(
                id=workflow_id,
                name=name,
                slug=slug,
                description=description,
                tags=tags,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = WorkflowCreateRequest(
        name="Test Workflow",
        slug="test-workflow",
        description="A test workflow",
        tags=["test"],
        actor="admin",
    )

    result = await create_workflow(request, Repository())

    assert result.id == workflow_id
    assert result.name == "Test Workflow"
    assert result.slug == "test-workflow"


@pytest.mark.asyncio()
async def test_get_workflow_returns_workflow() -> None:
    """Get workflow endpoint returns the requested workflow."""
    workflow_id = uuid4()

    class Repository:
        async def get_workflow(self, wf_id):
            return Workflow(
                id=wf_id,
                name="Test Workflow",
                slug="test-workflow",
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = await get_workflow(workflow_id, Repository())

    assert result.id == workflow_id
    assert result.name == "Test Workflow"


@pytest.mark.asyncio()
async def test_get_workflow_not_found() -> None:
    """Get workflow endpoint raises 404 for missing workflow."""
    workflow_id = uuid4()

    class Repository:
        async def get_workflow(self, wf_id):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow(workflow_id, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_update_workflow_returns_updated() -> None:
    """Update workflow endpoint returns the updated workflow."""
    workflow_id = uuid4()

    class Repository:
        async def update_workflow(
            self, wf_id, name, description, tags, is_archived, actor
        ):
            return Workflow(
                id=wf_id,
                name=name or "Test Workflow",
                slug="test-workflow",
                description=description,
                tags=tags or [],
                is_archived=is_archived,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = WorkflowUpdateRequest(
        name="Updated Workflow",
        description="Updated description",
        tags=["updated"],
        is_archived=False,
        actor="admin",
    )

    result = await update_workflow(workflow_id, request, Repository())

    assert result.id == workflow_id
    assert result.name == "Updated Workflow"


@pytest.mark.asyncio()
async def test_update_workflow_not_found() -> None:
    """Update workflow endpoint raises 404 for missing workflow."""
    workflow_id = uuid4()

    class Repository:
        async def update_workflow(
            self, wf_id, name, description, tags, is_archived, actor
        ):
            raise WorkflowNotFoundError("not found")

    request = WorkflowUpdateRequest(
        name="Updated Workflow",
        actor="admin",
    )

    with pytest.raises(HTTPException) as exc_info:
        await update_workflow(workflow_id, request, Repository())

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_archive_workflow_returns_archived() -> None:
    """Archive workflow endpoint returns the archived workflow."""
    workflow_id = uuid4()

    class Repository:
        async def archive_workflow(self, wf_id, actor):
            return Workflow(
                id=wf_id,
                name="Test Workflow",
                slug="test-workflow",
                is_archived=True,
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = await archive_workflow(workflow_id, Repository(), actor="admin")

    assert result.id == workflow_id
    assert result.is_archived is True


@pytest.mark.asyncio()
async def test_archive_workflow_not_found() -> None:
    """Archive workflow endpoint raises 404 for missing workflow."""
    workflow_id = uuid4()

    class Repository:
        async def archive_workflow(self, wf_id, actor):
            raise WorkflowNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        await archive_workflow(workflow_id, Repository(), actor="admin")

    assert exc_info.value.status_code == 404
