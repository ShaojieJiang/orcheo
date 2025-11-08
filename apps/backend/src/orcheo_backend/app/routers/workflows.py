"""Workflow CRUD and version management routes."""

from __future__ import annotations
import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status
from orcheo.graph.ingestion import ScriptIngestionError, ingest_langgraph_script
from orcheo.models.workflow import (
    Workflow,
    WorkflowVersion,
    generate_publish_token,
    hash_publish_token,
    mask_publish_token,
)
from orcheo_backend.app.dependencies import RepositoryDep
from orcheo_backend.app.errors import raise_not_found
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowPublishStateError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.schemas import (
    WorkflowCreateRequest,
    WorkflowPublishRequest,
    WorkflowPublishResponse,
    WorkflowPublishRevokeRequest,
    WorkflowPublishRotateRequest,
    WorkflowUpdateRequest,
    WorkflowVersionCreateRequest,
    WorkflowVersionDiffResponse,
    WorkflowVersionIngestRequest,
)


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/workflows", response_model=list[Workflow])
async def list_workflows(
    repository: RepositoryDep,
    include_archived: bool = False,
) -> list[Workflow]:
    """Return workflows, excluding archived ones by default."""
    return await repository.list_workflows(include_archived=include_archived)


@router.post(
    "/workflows",
    response_model=Workflow,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    request: WorkflowCreateRequest,
    repository: RepositoryDep,
) -> Workflow:
    """Create a new workflow entry."""
    return await repository.create_workflow(
        name=request.name,
        slug=request.slug,
        description=request.description,
        tags=request.tags,
        actor=request.actor,
    )


@router.get("/workflows/{workflow_id}", response_model=Workflow)
async def get_workflow(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> Workflow:
    """Fetch a single workflow by its identifier."""
    try:
        return await repository.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.put("/workflows/{workflow_id}", response_model=Workflow)
async def update_workflow(
    workflow_id: UUID,
    request: WorkflowUpdateRequest,
    repository: RepositoryDep,
) -> Workflow:
    """Update attributes of an existing workflow."""
    try:
        return await repository.update_workflow(
            workflow_id,
            name=request.name,
            description=request.description,
            tags=request.tags,
            is_archived=request.is_archived,
            actor=request.actor,
        )
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.delete("/workflows/{workflow_id}", response_model=Workflow)
async def archive_workflow(
    workflow_id: UUID,
    repository: RepositoryDep,
    actor: str = Query("system"),
) -> Workflow:
    """Archive a workflow via the delete verb."""
    try:
        return await repository.archive_workflow(workflow_id, actor=actor)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.post(
    "/workflows/{workflow_id}/versions",
    response_model=WorkflowVersion,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_version(
    workflow_id: UUID,
    request: WorkflowVersionCreateRequest,
    repository: RepositoryDep,
) -> WorkflowVersion:
    """Create a new version for the specified workflow."""
    try:
        return await repository.create_version(
            workflow_id,
            graph=request.graph,
            metadata=request.metadata,
            notes=request.notes,
            created_by=request.created_by,
        )
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.post(
    "/workflows/{workflow_id}/versions/ingest",
    response_model=WorkflowVersion,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_workflow_version(
    workflow_id: UUID,
    request: WorkflowVersionIngestRequest,
    repository: RepositoryDep,
) -> WorkflowVersion:
    """Create a workflow version from a LangGraph Python script."""
    try:
        graph_payload = ingest_langgraph_script(
            request.script,
            entrypoint=request.entrypoint,
        )
    except ScriptIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    try:
        return await repository.create_version(
            workflow_id,
            graph=graph_payload,
            metadata=request.metadata,
            notes=request.notes,
            created_by=request.created_by,
        )
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.get(
    "/workflows/{workflow_id}/versions",
    response_model=list[WorkflowVersion],
)
async def list_workflow_versions(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> list[WorkflowVersion]:
    """Return the versions associated with a workflow."""
    try:
        return await repository.list_versions(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.get(
    "/workflows/{workflow_id}/versions/{version_number}",
    response_model=WorkflowVersion,
)
async def get_workflow_version(
    workflow_id: UUID,
    version_number: int,
    repository: RepositoryDep,
) -> WorkflowVersion:
    """Return a specific workflow version by number."""
    try:
        return await repository.get_version_by_number(workflow_id, version_number)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        raise_not_found("Workflow version not found", exc)


@router.get(
    "/workflows/{workflow_id}/versions/{base_version}/diff/{target_version}",
    response_model=WorkflowVersionDiffResponse,
)
async def diff_workflow_versions(
    workflow_id: UUID,
    base_version: int,
    target_version: int,
    repository: RepositoryDep,
) -> WorkflowVersionDiffResponse:
    """Generate a diff between two workflow versions."""
    try:
        diff = await repository.diff_versions(workflow_id, base_version, target_version)
        return WorkflowVersionDiffResponse(
            base_version=diff.base_version,
            target_version=diff.target_version,
            diff=diff.diff,
        )
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        raise_not_found("Workflow version not found", exc)


def _publish_response(workflow: Workflow, token: str | None) -> WorkflowPublishResponse:
    message: str | None = None
    if token:
        message = "Store this publish token securely. It will not be shown again."
    return WorkflowPublishResponse(
        workflow=workflow,
        publish_token=token,
        message=message,
    )


@router.post(
    "/workflows/{workflow_id}/publish",
    response_model=WorkflowPublishResponse,
    status_code=status.HTTP_201_CREATED,
)
async def publish_workflow(
    workflow_id: UUID,
    request: WorkflowPublishRequest,
    repository: RepositoryDep,
) -> WorkflowPublishResponse:
    """Publish a workflow and generate a new shareable token."""
    try:
        token = generate_publish_token()
        workflow = await repository.publish_workflow(
            workflow_id,
            publish_token_hash=hash_publish_token(token),
            require_login=request.require_login,
            actor=request.actor,
        )
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowPublishStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "code": "workflow.publish.invalid_state"},
        ) from exc

    logger.info(
        "Workflow published",
        extra={
            "workflow_id": str(workflow.id),
            "actor": request.actor,
            "require_login": request.require_login,
            "publish_token": mask_publish_token(workflow.publish_token_hash or ""),
        },
    )
    return _publish_response(workflow, token)


@router.post(
    "/workflows/{workflow_id}/publish/rotate",
    response_model=WorkflowPublishResponse,
)
async def rotate_publish_token(
    workflow_id: UUID,
    request: WorkflowPublishRotateRequest,
    repository: RepositoryDep,
) -> WorkflowPublishResponse:
    """Rotate the publish token for the specified workflow."""
    try:
        token = generate_publish_token()
        workflow = await repository.rotate_publish_token(
            workflow_id,
            publish_token_hash=hash_publish_token(token),
            actor=request.actor,
        )
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowPublishStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "code": "workflow.publish.invalid_state"},
        ) from exc

    logger.info(
        "Workflow publish token rotated",
        extra={
            "workflow_id": str(workflow.id),
            "actor": request.actor,
            "publish_token": mask_publish_token(workflow.publish_token_hash or ""),
        },
    )
    return _publish_response(workflow, token)


@router.post(
    "/workflows/{workflow_id}/publish/revoke",
    response_model=Workflow,
)
async def revoke_workflow_publish(
    workflow_id: UUID,
    request: WorkflowPublishRevokeRequest,
    repository: RepositoryDep,
) -> Workflow:
    """Revoke public access to the workflow."""
    try:
        workflow = await repository.revoke_publish(workflow_id, actor=request.actor)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowPublishStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": str(exc), "code": "workflow.publish.invalid_state"},
        ) from exc

    masked_previous = "unknown"
    if workflow.audit_log:
        last_event = workflow.audit_log[-1]
        if last_event.metadata.get("previous_token"):
            masked_previous = str(last_event.metadata["previous_token"])

    logger.info(
        "Workflow publish access revoked",
        extra={
            "workflow_id": str(workflow.id),
            "actor": request.actor,
            "previous_token": masked_previous,
        },
    )

    return workflow


__all__ = ["router"]
