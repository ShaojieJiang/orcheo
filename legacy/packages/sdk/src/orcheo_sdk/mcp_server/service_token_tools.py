"""Service token MCP tools."""

from orcheo_sdk.mcp_server import tools
from orcheo_sdk.mcp_server.server import mcp


@mcp.tool()
def list_service_tokens(profile: str | None = None) -> dict:
    """List all service tokens."""
    return tools.list_service_tokens(profile=profile)


@mcp.tool()
def show_service_token(
    token_id: str,
    profile: str | None = None,
) -> dict:
    """Display details for a specific service token."""
    return tools.show_service_token(token_id=token_id, profile=profile)


@mcp.tool()
def create_service_token(
    identifier: str | None = None,
    scopes: list[str] | None = None,
    workspace_ids: list[str] | None = None,
    expires_in_seconds: int | None = None,
    profile: str | None = None,
) -> dict:
    """Create a new service token."""
    return tools.create_service_token(
        identifier=identifier,
        scopes=scopes,
        workspace_ids=workspace_ids,
        expires_in_seconds=expires_in_seconds,
        profile=profile,
    )


@mcp.tool()
def rotate_service_token(
    token_id: str,
    overlap_seconds: int = 300,
    expires_in_seconds: int | None = None,
    profile: str | None = None,
) -> dict:
    """Rotate a service token, generating a new secret."""
    return tools.rotate_service_token(
        token_id=token_id,
        overlap_seconds=overlap_seconds,
        expires_in_seconds=expires_in_seconds,
        profile=profile,
    )


@mcp.tool()
def revoke_service_token(
    token_id: str,
    reason: str,
    profile: str | None = None,
) -> dict:
    """Revoke a service token immediately."""
    return tools.revoke_service_token(
        token_id=token_id,
        reason=reason,
        profile=profile,
    )


__all__ = [
    "create_service_token",
    "list_service_tokens",
    "revoke_service_token",
    "rotate_service_token",
    "show_service_token",
]
