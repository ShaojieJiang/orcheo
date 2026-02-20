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
    CredentialSecretResponse,
    CredentialUpdateRequest,
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


@router.get(
    "/credentials/{credential_id}/secret",
    response_model=CredentialSecretResponse,
)
def reveal_credential_secret(
    credential_id: UUID,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> CredentialSecretResponse:
    """Reveal and return the decrypted credential secret."""
    context = credential_context_from_workflow(workflow_id)
    try:
        secret = vault.reveal_secret(credential_id=credential_id, context=context)
    except CredentialNotFoundError as exc:
        raise_not_found("Credential not found", exc)
    except WorkflowScopeError as exc:
        raise_scope_error(exc)
    return CredentialSecretResponse(id=str(credential_id), secret=secret)


@router.patch(
    "/credentials/{credential_id}",
    response_model=CredentialVaultEntryResponse,
)
def update_credential(
    credential_id: UUID,
    request: CredentialUpdateRequest,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> CredentialVaultEntryResponse:
    """Update credential metadata and optionally rotate the secret."""
    effective_workflow_id = workflow_id or request.workflow_id
    if request.access in {"private", "shared"} and effective_workflow_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=("workflow_id is required when access is set to private or shared"),
        )
    context = credential_context_from_workflow(effective_workflow_id)
    scope = (
        scope_from_access(request.access, effective_workflow_id)
        if request.access is not None
        else None
    )
    try:
        metadata = vault.update_credential(
            credential_id=credential_id,
            actor=request.actor,
            name=request.name,
            provider=request.provider,
            secret=request.secret,
            scope=scope,
            context=context,
        )
    except CredentialNotFoundError as exc:
        raise_not_found("Credential not found", exc)
    except WorkflowScopeError as exc:
        raise_scope_error(exc)
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
    if request.access is not None and request.access != response.access:
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
