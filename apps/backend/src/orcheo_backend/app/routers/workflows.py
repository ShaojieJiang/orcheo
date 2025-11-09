"""Workflow CRUD and version management routes."""

from __future__ import annotations
import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from orcheo.graph.ingestion import ScriptIngestionError, ingest_langgraph_script
from orcheo.models.workflow import (
    Workflow,
    WorkflowVersion,
)
from orcheo_backend.app.authentication import (
    AuthorizationError,
    AuthorizationPolicy,
    get_authorization_policy,
)
from orcheo_backend.app.chatkit_runtime import resolve_chatkit_token_issuer
from orcheo_backend.app.chatkit_tokens import ChatKitSessionTokenIssuer
from orcheo_backend.app.dependencies import RepositoryDep
from orcheo_backend.app.errors import raise_not_found
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowPublishStateError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.schemas.chatkit import ChatKitSessionResponse
from orcheo_backend.app.schemas.workflows import (
    WorkflowCreateRequest,
    WorkflowPublishRequest,
    WorkflowPublishResponse,
    WorkflowPublishRevokeRequest,
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


def _publish_response(
    workflow: Workflow,
    *,
    message: str | None = None,
) -> WorkflowPublishResponse:
    return WorkflowPublishResponse(
        workflow=workflow,
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
    """Publish a workflow and expose it for ChatKit access."""
    try:
        workflow = await repository.publish_workflow(
            workflow_id,
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
        },
    )
    return _publish_response(
        workflow,
        message="Workflow is now public via the /chat route.",
    )


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

    logger.info(
        "Workflow publish access revoked",
        extra={
            "workflow_id": str(workflow.id),
            "actor": request.actor,
        },
    )

    return workflow


def _select_primary_workspace(workspace_ids: frozenset[str]) -> str | None:
    if len(workspace_ids) == 1:
        return next(iter(workspace_ids))
    return None


def _extract_workflow_workspace_ids(workflow: Workflow) -> frozenset[str]:
    """Return workspace identifiers encoded within workflow tags."""
    workspaces = {
        tag.split(":", 1)[1]
        for tag in workflow.tags
        if tag.startswith("workspace:") and ":" in tag
    }
    return frozenset(workspaces)


def _resolve_workflow_owner(workflow: Workflow) -> str | None:
    """Return the actor associated with the workflow's creation event."""
    if not workflow.audit_log:
        return None
    return workflow.audit_log[0].actor


@router.post(
    "/workflows/{workflow_id}/chatkit/session",
    response_model=ChatKitSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def create_workflow_chatkit_session(
    workflow_id: UUID,
    repository: RepositoryDep,
    policy: AuthorizationPolicy = Depends(get_authorization_policy),  # noqa: B008
    issuer: ChatKitSessionTokenIssuer = Depends(resolve_chatkit_token_issuer),  # noqa: B008
) -> ChatKitSessionResponse:
    """Issue a ChatKit JWT scoped to the workflow for authenticated Canvas users."""
    context = policy.require_authenticated()
    policy.require_scopes("workflows:read", "workflows:execute")

    try:
        workflow = await repository.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)

    workflow_workspaces = _extract_workflow_workspace_ids(workflow)
    if workflow_workspaces:
        if not context.workspace_ids:
            raise AuthorizationError(
                "Workspace access required for workflow.",
                code="auth.workspace_forbidden",
            )
        if not workflow_workspaces.intersection(context.workspace_ids):
            raise AuthorizationError(
                "Workspace access denied for workflow.",
                code="auth.workspace_forbidden",
            )
    else:
        owner = _resolve_workflow_owner(workflow)
        if owner is not None and owner != context.subject:
            raise AuthorizationError(
                "Workflow access denied for caller.",
                code="auth.forbidden",
            )

    metadata = {
        "workflow_id": str(workflow.id),
        "workflow_name": workflow.name,
        "source": "canvas",
    }
    primary_workspace = _select_primary_workspace(context.workspace_ids)
    token, expires_at = issuer.mint_session(
        subject=context.subject,
        identity_type=context.identity_type,
        token_id=context.token_id,
        workspace_ids=context.workspace_ids,
        primary_workspace_id=primary_workspace,
        workflow_id=workflow.id,
        scopes=context.scopes,
        metadata=metadata,
        user=None,
        assistant=None,
        extra={"interface": "canvas_modal"},
    )

    logger.info(
        "Issued workflow ChatKit session token",
        extra={
            "workflow_id": str(workflow.id),
            "subject": context.subject,
            "workspace_id": primary_workspace or "<multiple>",
        },
    )
    return ChatKitSessionResponse(client_secret=token, expires_at=expires_at)


__all__ = ["router"]
