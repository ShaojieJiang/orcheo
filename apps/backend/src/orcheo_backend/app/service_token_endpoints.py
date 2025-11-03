"""FastAPI endpoints for service token management."""

from __future__ import annotations
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from orcheo_backend.app.authentication import (
    AuthorizationPolicy,
    ServiceTokenRecord,
    get_authorization_policy,
    get_service_token_manager,
)


class CreateServiceTokenRequest(BaseModel):
    """Request to create a new service token."""

    identifier: str | None = Field(
        None,
        description="Optional identifier for the token (auto-generated if omitted)",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Scopes/permissions granted to the token",
    )
    workspace_ids: list[str] = Field(
        default_factory=list,
        description="Workspace IDs the token can access",
    )
    expires_in_seconds: int | None = Field(
        None,
        ge=60,
        description="Optional expiration time in seconds (no expiration if omitted)",
    )


class ServiceTokenResponse(BaseModel):
    """Response containing service token details."""

    identifier: str = Field(description="Unique identifier for the token")
    secret: str | None = Field(
        None,
        description="Raw token secret (only shown once on creation)",
    )
    scopes: list[str] = Field(description="Scopes granted to the token")
    workspace_ids: list[str] = Field(description="Workspaces the token can access")
    issued_at: datetime | None = Field(description="Token issuance timestamp")
    expires_at: datetime | None = Field(description="Token expiration timestamp")
    last_used_at: datetime | None = Field(None, description="Last usage timestamp")
    use_count: int | None = Field(None, description="Number of times token was used")
    revoked_at: datetime | None = Field(None, description="Revocation timestamp")
    revocation_reason: str | None = Field(None, description="Reason for revocation")
    rotated_to: str | None = Field(None, description="Identifier of replacement token")
    message: str | None = Field(None, description="Additional information")


class RotateServiceTokenRequest(BaseModel):
    """Request to rotate a service token."""

    overlap_seconds: int = Field(
        default=300,
        ge=0,
        description="Grace period where both old and new tokens are valid",
    )
    expires_in_seconds: int | None = Field(
        None,
        ge=60,
        description="Optional expiration time for new token in seconds",
    )


class RevokeServiceTokenRequest(BaseModel):
    """Request to revoke a service token."""

    reason: str = Field(description="Reason for revoking the token")


class ServiceTokenListResponse(BaseModel):
    """Response containing list of service tokens."""

    tokens: list[ServiceTokenResponse] = Field(description="List of service tokens")
    total: int = Field(description="Total number of tokens")


router = APIRouter(prefix="/admin/service-tokens", tags=["admin", "tokens"])


def _record_to_response(
    record: ServiceTokenRecord,
    *,
    secret: str | None = None,
    message: str | None = None,
) -> ServiceTokenResponse:
    """Convert ServiceTokenRecord to API response."""
    return ServiceTokenResponse(
        identifier=record.identifier,
        secret=secret,
        scopes=sorted(record.scopes),
        workspace_ids=sorted(record.workspace_ids),
        issued_at=record.issued_at,
        expires_at=record.expires_at,
        last_used_at=None,  # Will be populated from audit log if needed
        use_count=None,
        revoked_at=record.revoked_at,
        revocation_reason=record.revocation_reason,
        rotated_to=record.rotated_to,
        message=message,
    )


@router.post(
    "", response_model=ServiceTokenResponse, status_code=status.HTTP_201_CREATED
)
async def create_service_token(
    request: CreateServiceTokenRequest,
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
) -> ServiceTokenResponse:
    """Create a new service token.

    Requires 'admin:tokens:write' scope.
    The secret is only shown once in the response and cannot be retrieved later.
    """
    policy.require_authenticated()
    policy.require_scopes("admin:tokens:write")

    token_manager = get_service_token_manager()

    secret, record = await token_manager.mint(
        identifier=request.identifier,
        scopes=request.scopes,
        workspace_ids=request.workspace_ids,
        expires_in=request.expires_in_seconds,
    )

    return _record_to_response(
        record,
        secret=secret,
        message="Store this token securely. It will not be shown again.",
    )


@router.get("", response_model=ServiceTokenListResponse)
async def list_service_tokens(
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
) -> ServiceTokenListResponse:
    """List all service tokens.

    Requires 'admin:tokens:read' scope.
    Secrets are never returned in the list.
    """
    policy.require_authenticated()
    policy.require_scopes("admin:tokens:read")

    token_manager = get_service_token_manager()
    records = await token_manager.all()

    tokens = [_record_to_response(record) for record in records]
    return ServiceTokenListResponse(tokens=tokens, total=len(tokens))


@router.get("/{token_id}", response_model=ServiceTokenResponse)
async def get_service_token(
    token_id: str,
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
) -> ServiceTokenResponse:
    """Get details for a specific service token.

    Requires 'admin:tokens:read' scope.
    """
    policy.require_authenticated()
    policy.require_scopes("admin:tokens:read")

    token_manager = get_service_token_manager()
    record = await token_manager._repository.find_by_id(token_id)

    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Service token '{token_id}' not found",
                "code": "token.not_found",
            },
        )

    return _record_to_response(record)


@router.post("/{token_id}/rotate", response_model=ServiceTokenResponse)
async def rotate_service_token(
    token_id: str,
    request: RotateServiceTokenRequest,
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
) -> ServiceTokenResponse:
    """Rotate a service token, generating a new secret.

    Requires 'admin:tokens:write' scope.
    The old token remains valid during the overlap period.
    The new secret is only shown once.
    """
    policy.require_authenticated()
    policy.require_scopes("admin:tokens:write")

    token_manager = get_service_token_manager()

    try:
        secret, new_record = await token_manager.rotate(
            token_id,
            overlap_seconds=request.overlap_seconds,
            expires_in=request.expires_in_seconds,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Service token '{token_id}' not found",
                "code": "token.not_found",
            },
        ) from None

    message = (
        f"New token created. Old token '{token_id}' "
        f"valid for {request.overlap_seconds}s."
    )
    return _record_to_response(new_record, secret=secret, message=message)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_service_token(
    token_id: str,
    request: RevokeServiceTokenRequest,
    policy: Annotated[AuthorizationPolicy, Depends(get_authorization_policy)],
) -> None:
    """Revoke a service token immediately.

    Requires 'admin:tokens:write' scope.
    The token will no longer be usable for authentication.
    """
    policy.require_authenticated()
    policy.require_scopes("admin:tokens:write")

    token_manager = get_service_token_manager()

    try:
        await token_manager.revoke(token_id, reason=request.reason)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": f"Service token '{token_id}' not found",
                "code": "token.not_found",
            },
        ) from None


__all__ = ["router"]
