"""Credential metadata routes."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, HTTPException, Response, status
from orcheo.vault import (
    CredentialNotFoundError,
    DuplicateCredentialNameError,
    WorkflowScopeError,
)
from orcheo_backend.app.credential_utils import (
    credential_to_response,
    scope_from_access,
)
from orcheo_backend.app.dependencies import (
    VaultDep,
    WorkflowIdQuery,
    credential_context_from_workflow,
)
from orcheo_backend.app.errors import raise_not_found, raise_scope_error
from orcheo_backend.app.schemas.credentials import (
    CredentialCreateRequest,
    CredentialVaultEntryResponse,
)


router = APIRouter()


@router.get(
    "/credentials",
    response_model=list[CredentialVaultEntryResponse],
)
def list_credentials(
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> list[CredentialVaultEntryResponse]:
    """Return credential metadata visible to the caller."""
    context = credential_context_from_workflow(workflow_id)
    credentials = vault.list_credentials(context=context)
    return [credential_to_response(metadata) for metadata in credentials]


@router.post(
    "/credentials",
    response_model=CredentialVaultEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_credential(
    request: CredentialCreateRequest,
    vault: VaultDep,
) -> CredentialVaultEntryResponse:
    """Persist a new credential in the vault."""
    scope = scope_from_access(request.access, request.workflow_id)
    try:
        metadata = vault.create_credential(
            name=request.name,
            provider=request.provider,
            scopes=request.scopes,
            secret=request.secret,
            actor=request.actor,
            scope=scope,
            kind=request.kind,
        )
    except DuplicateCredentialNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    response = credential_to_response(metadata)
    if request.access != response.access:
        response = response.model_copy(update={"access": request.access})
    return response


@router.delete(
    "/credentials/{credential_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_credential(
    credential_id: UUID,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> Response:
    """Delete a credential."""
    context = credential_context_from_workflow(workflow_id)
    try:
        vault.delete_credential(credential_id, context=context)
    except CredentialNotFoundError as exc:
        raise_not_found("Credential not found", exc)
    except WorkflowScopeError as exc:
        raise_scope_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
