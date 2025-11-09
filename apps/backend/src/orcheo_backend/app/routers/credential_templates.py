"""Credential template routes."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, HTTPException, Response, status
from orcheo.vault import (
    CredentialTemplateNotFoundError,
    WorkflowScopeError,
)
from orcheo_backend.app.credential_utils import (
    build_oauth_tokens,
    build_policy,
    build_scope,
    template_to_response,
)
from orcheo_backend.app.dependencies import (
    CredentialServiceDep,
    VaultDep,
    WorkflowIdQuery,
    credential_context_from_workflow,
)
from orcheo_backend.app.errors import raise_not_found, raise_scope_error
from orcheo_backend.app.schemas.credentials import (
    CredentialIssuanceRequest,
    CredentialIssuanceResponse,
    CredentialTemplateCreateRequest,
    CredentialTemplateResponse,
    CredentialTemplateUpdateRequest,
)


router = APIRouter()


@router.get(
    "/credentials/templates",
    response_model=list[CredentialTemplateResponse],
)
def list_credential_templates(
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> list[CredentialTemplateResponse]:
    """List credential templates visible to the caller."""
    context = credential_context_from_workflow(workflow_id)
    templates = vault.list_templates(context=context)
    return [template_to_response(template) for template in templates]


@router.post(
    "/credentials/templates",
    response_model=CredentialTemplateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_credential_template(
    request: CredentialTemplateCreateRequest,
    vault: VaultDep,
) -> CredentialTemplateResponse:
    """Create a new credential template."""
    scope = build_scope(request.scope)
    policy = build_policy(request.issuance_policy)
    template = vault.create_template(
        name=request.name,
        provider=request.provider,
        scopes=request.scopes,
        actor=request.actor,
        description=request.description,
        scope=scope,
        kind=request.kind,
        issuance_policy=policy,
    )
    return template_to_response(template)


@router.get(
    "/credentials/templates/{template_id}",
    response_model=CredentialTemplateResponse,
)
def get_credential_template(
    template_id: UUID,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> CredentialTemplateResponse:
    """Return a single credential template."""
    context = credential_context_from_workflow(workflow_id)
    try:
        template = vault.get_template(template_id=template_id, context=context)
        return template_to_response(template)
    except CredentialTemplateNotFoundError as exc:
        raise_not_found("Credential template not found", exc)
    except WorkflowScopeError as exc:
        raise_scope_error(exc)


@router.patch(
    "/credentials/templates/{template_id}",
    response_model=CredentialTemplateResponse,
)
def update_credential_template(
    template_id: UUID,
    request: CredentialTemplateUpdateRequest,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> CredentialTemplateResponse:
    """Update credential template metadata."""
    context = credential_context_from_workflow(workflow_id)
    scope = build_scope(request.scope)
    policy = build_policy(request.issuance_policy)

    try:
        template = vault.update_template(
            template_id=template_id,
            actor=request.actor,
            name=request.name,
            description=request.description,
            scopes=request.scopes,
            scope=scope,
            kind=request.kind,
            issuance_policy=policy,
            context=context,
        )
        return template_to_response(template)
    except CredentialTemplateNotFoundError as exc:
        raise_not_found("Credential template not found", exc)
    except WorkflowScopeError as exc:
        raise_scope_error(exc)


@router.delete(
    "/credentials/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_credential_template(
    template_id: UUID,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> Response:
    """Delete a credential template."""
    context = credential_context_from_workflow(workflow_id)
    try:
        vault.delete_template(template_id, context=context)
    except CredentialTemplateNotFoundError as exc:
        raise_not_found("Credential template not found", exc)
    except WorkflowScopeError as exc:
        raise_scope_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/credentials/templates/{template_id}/issue",
    response_model=CredentialIssuanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def issue_credential_from_template(
    template_id: UUID,
    request: CredentialIssuanceRequest,
    service: CredentialServiceDep,
) -> CredentialIssuanceResponse:
    """Issue a credential based on a stored template."""
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential service is not configured.",
        )

    context = credential_context_from_workflow(request.workflow_id)
    tokens = build_oauth_tokens(request.oauth_tokens)
    try:
        metadata = service.issue_from_template(
            template_id=template_id,
            secret=request.secret,
            actor=request.actor,
            name=request.name,
            scopes=request.scopes,
            context=context,
            oauth_tokens=tokens,
        )
    except CredentialTemplateNotFoundError as exc:
        raise_not_found("Credential template not found", exc)
    except WorkflowScopeError as exc:
        raise_scope_error(exc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return CredentialIssuanceResponse(
        credential_id=str(metadata.id),
        name=metadata.name,
        provider=metadata.provider,
        kind=metadata.kind,
        template_id=str(metadata.template_id) if metadata.template_id else None,
        created_at=metadata.created_at,
        updated_at=metadata.updated_at,
    )


__all__ = ["router"]
