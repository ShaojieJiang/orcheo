from __future__ import annotations
from uuid import uuid4
import pytest
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowRepository,
)


@pytest.mark.asyncio()
async def test_create_and_list_workflows(repository: WorkflowRepository) -> None:
    """Workflows can be created and listed with deep copies returned."""

    created = await repository.create_workflow(
        name="Test Flow",
        slug=None,
        description="Example workflow",
        tags=["alpha"],
        actor="tester",
    )

    workflows = await repository.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].id == created.id
    assert workflows[0].slug == "test-flow"

    # Returned instances must be detached copies.
    workflows[0].name = "mutated"
    fresh = await repository.get_workflow(created.id)
    assert fresh.name == "Test Flow"


@pytest.mark.asyncio()
async def test_list_workflows_excludes_archived_by_default(
    repository: WorkflowRepository,
) -> None:
    """List workflows excludes archived workflows by default."""

    active = await repository.create_workflow(
        name="Active Flow",
        slug=None,
        description="Active workflow",
        tags=[],
        actor="tester",
    )

    archived_workflow = await repository.create_workflow(
        name="Archived Flow",
        slug=None,
        description="Archived workflow",
        tags=[],
        actor="tester",
    )

    await repository.archive_workflow(archived_workflow.id, actor="tester")

    workflows = await repository.list_workflows()
    assert len(workflows) == 1
    assert workflows[0].id == active.id
    assert not workflows[0].is_archived


@pytest.mark.asyncio()
async def test_list_workflows_includes_archived_when_requested(
    repository: WorkflowRepository,
) -> None:
    """List workflows includes archived workflows when include_archived=True."""

    active = await repository.create_workflow(
        name="Active Flow",
        slug=None,
        description="Active workflow",
        tags=[],
        actor="tester",
    )

    archived_workflow = await repository.create_workflow(
        name="Archived Flow",
        slug=None,
        description="Archived workflow",
        tags=[],
        actor="tester",
    )

    await repository.archive_workflow(archived_workflow.id, actor="tester")

    workflows = await repository.list_workflows(include_archived=True)
    assert len(workflows) == 2

    active_found = False
    archived_found = False

    for wf in workflows:
        if wf.id == active.id:
            active_found = True
            assert not wf.is_archived
        elif wf.id == archived_workflow.id:
            archived_found = True
            assert wf.is_archived

    assert active_found
    assert archived_found


@pytest.mark.asyncio()
async def test_update_and_archive_workflow(
    repository: WorkflowRepository,
) -> None:
    """Updating a workflow touches each branch of metadata normalization."""

    created = await repository.create_workflow(
        name="Original",
        slug="custom-slug",
        description="Desc",
        tags=["a"],
        actor="author",
    )

    updated = await repository.update_workflow(
        created.id,
        name="Renamed",
        description="New desc",
        tags=["b"],
        is_archived=None,
        actor="editor",
    )
    assert updated.name == "Renamed"
    assert updated.description == "New desc"
    assert updated.tags == ["b"]
    assert updated.is_archived is False

    archived = await repository.archive_workflow(created.id, actor="editor")
    assert archived.is_archived is True

    unchanged = await repository.update_workflow(
        created.id,
        name=None,
        description=None,
        tags=["b"],
        is_archived=True,
        actor="editor",
    )
    assert unchanged.tags == ["b"]
    assert unchanged.is_archived is True
    assert unchanged.audit_log[-1].metadata == {}


@pytest.mark.asyncio()
async def test_update_missing_workflow(repository: WorkflowRepository) -> None:
    """Updating a missing workflow raises an explicit error."""

    with pytest.raises(WorkflowNotFoundError):
        await repository.update_workflow(
            uuid4(),
            name=None,
            description=None,
            tags=None,
            is_archived=None,
            actor="tester",
        )
