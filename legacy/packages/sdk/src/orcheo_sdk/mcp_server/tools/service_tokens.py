"""Service token MCP tools."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.mcp_server.config import get_api_client
from orcheo_sdk.services import (
    create_service_token_data,
    list_service_tokens_data,
    revoke_service_token_data,
    rotate_service_token_data,
    show_service_token_data,
)


def list_service_tokens(
    profile: str | None = None,
) -> dict[str, Any]:
    """List all service tokens."""
    client, _ = get_api_client(profile=profile)
    return list_service_tokens_data(client)


def show_service_token(
    token_id: str,
    profile: str | None = None,
) -> dict[str, Any]:
    """Display details for a specific service token."""
    client, _ = get_api_client(profile=profile)
    return show_service_token_data(client, token_id)


def create_service_token(
    identifier: str | None = None,
    scopes: list[str] | None = None,
    workspace_ids: list[str] | None = None,
    expires_in_seconds: int | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Create a new service token."""
    client, _ = get_api_client(profile=profile)
    return create_service_token_data(
        client,
        identifier=identifier,
        scopes=scopes,
        workspace_ids=workspace_ids,
        expires_in_seconds=expires_in_seconds,
    )


def rotate_service_token(
    token_id: str,
    overlap_seconds: int = 300,
    expires_in_seconds: int | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Rotate a service token, generating a new secret."""
    client, _ = get_api_client(profile=profile)
    return rotate_service_token_data(
        client,
        token_id,
        overlap_seconds=overlap_seconds,
        expires_in_seconds=expires_in_seconds,
    )


def revoke_service_token(
    token_id: str,
    reason: str,
    profile: str | None = None,
) -> dict[str, str]:
    """Revoke a service token immediately."""
    client, _ = get_api_client(profile=profile)
    return revoke_service_token_data(client, token_id, reason)


__all__ = [
    "create_service_token",
    "list_service_tokens",
    "revoke_service_token",
    "rotate_service_token",
    "show_service_token",
]
