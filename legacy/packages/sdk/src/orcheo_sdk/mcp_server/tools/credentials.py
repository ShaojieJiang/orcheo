"""Credential management MCP tools."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.mcp_server.config import get_api_client
from orcheo_sdk.services import (
    create_credential_data,
    delete_credential_data,
    list_credentials_data,
)


def list_credentials(
    workflow_id: str | None = None,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """List credentials visible to the caller."""
    client, _ = get_api_client(profile=profile)
    return list_credentials_data(client, workflow_id=workflow_id)


def create_credential(
    name: str,
    provider: str,
    secret: str,
    actor: str = "mcp",
    access: str = "private",
    workflow_id: str | None = None,
    scopes: list[str] | None = None,
    kind: str = "secret",
    profile: str | None = None,
) -> dict[str, Any]:
    """Create a credential via the vault API."""
    client, _ = get_api_client(profile=profile)
    return create_credential_data(
        client,
        name,
        provider,
        secret,
        actor=actor,
        access=access,
        workflow_id=workflow_id,
        scopes=scopes,
        kind=kind,
    )


def delete_credential(
    credential_id: str,
    workflow_id: str | None = None,
    profile: str | None = None,
) -> dict[str, str]:
    """Delete a credential from the vault."""
    client, _ = get_api_client(profile=profile)
    return delete_credential_data(client, credential_id, workflow_id=workflow_id)


__all__ = ["create_credential", "delete_credential", "list_credentials"]
