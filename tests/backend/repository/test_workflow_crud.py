from __future__ import annotations
from uuid import uuid4
import pytest
from orcheo_backend.app.repository import (
    WorkflowHandleConflictError,
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


@pytest.mark.asyncio()
async def test_create_workflow_rejects_uuid_like_handle(
    repository: WorkflowRepository,
) -> None:
    """Workflow handles cannot use a UUID format."""

    with pytest.raises(ValueError, match="must not use a UUID format"):
        await repository.create_workflow(
            name="UUID Handle",
            handle="550e8400-e29b-41d4-a716-446655440000",
            slug=None,
            description=None,
            tags=None,
            actor="tester",
        )


@pytest.mark.asyncio()
async def test_update_workflow_rejects_uuid_like_handle(
    repository: WorkflowRepository,
) -> None:
    """Workflow updates validate handles even when bypassing the API layer."""

    created = await repository.create_workflow(
        name="Original",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    with pytest.raises(ValueError, match="must not use a UUID format"):
        await repository.update_workflow(
            created.id,
            name=None,
            handle="550e8400-e29b-41d4-a716-446655440000",
            description=None,
            tags=None,
            is_archived=None,
            actor="tester",
        )


@pytest.mark.asyncio()
async def test_resolve_workflow_ref_finds_archived_handle_when_requested(
    repository: WorkflowRepository,
) -> None:
    """Archived handles remain resolvable unless explicitly excluded."""

    archived = await repository.create_workflow(
        name="Archived",
        handle="shared-handle",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    await repository.archive_workflow(archived.id, actor="tester")

    resolved = await repository.resolve_workflow_ref("shared-handle")
    assert resolved == archived.id

    with pytest.raises(WorkflowNotFoundError):
        await repository.resolve_workflow_ref(
            "shared-handle",
            include_archived=False,
        )


@pytest.mark.asyncio()
async def test_update_workflow_updates_handle_and_resolves_new_ref(
    repository: WorkflowRepository,
) -> None:
    """Updating a workflow handle makes the new ref resolvable."""

    created = await repository.create_workflow(
        name="Handle Flow",
        handle="handle-flow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    updated = await repository.update_workflow(
        created.id,
        name=None,
        handle="renamed-flow",
        description=None,
        tags=None,
        is_archived=None,
        actor="tester",
    )

    assert updated.handle == "renamed-flow"
    assert await repository.resolve_workflow_ref("renamed-flow") == created.id


@pytest.mark.asyncio()
async def test_update_workflow_rejects_duplicate_active_handle(
    repository: WorkflowRepository,
) -> None:
    """Active workflows cannot reuse another active workflow handle."""

    await repository.create_workflow(
        name="Primary",
        handle="shared-handle",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    created = await repository.create_workflow(
        name="Secondary",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    with pytest.raises(WorkflowHandleConflictError):
        await repository.update_workflow(
            created.id,
            name=None,
            handle="shared-handle",
            description=None,
            tags=None,
            is_archived=None,
            actor="tester",
        )


@pytest.mark.asyncio()
async def test_update_workflow_allows_reusing_handle_for_archived_workflows(
    repository: WorkflowRepository,
) -> None:
    """Archived workflows may reuse an archived handle."""

    first = await repository.create_workflow(
        name="Archived Primary",
        handle="shared-handle",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    await repository.archive_workflow(first.id, actor="tester")

    second = await repository.create_workflow(
        name="Archived Secondary",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    updated = await repository.update_workflow(
        second.id,
        name=None,
        handle="shared-handle",
        description=None,
        tags=None,
        is_archived=True,
        actor="tester",
    )

    assert updated.handle == "shared-handle"
    assert updated.is_archived is True


@pytest.mark.asyncio()
async def test_resolve_workflow_ref_rejects_blank_value(
    repository: WorkflowRepository,
) -> None:
    """Blank workflow refs raise a not-found error."""

    with pytest.raises(WorkflowNotFoundError, match="workflow ref is empty"):
        await repository.resolve_workflow_ref("   ")
