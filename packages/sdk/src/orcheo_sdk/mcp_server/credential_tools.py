"""Credential management MCP tools."""

from orcheo_sdk.mcp_server import tools
from orcheo_sdk.mcp_server.server import mcp


@mcp.tool()
def list_credentials(
    workflow_id: str | None = None,
    profile: str | None = None,
) -> list[dict]:
    """List credentials visible to the caller."""
    return tools.list_credentials(workflow_id=workflow_id, profile=profile)


@mcp.tool()
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
) -> dict:
    """Create a credential via the vault API."""
    return tools.create_credential(
        name=name,
        provider=provider,
        secret=secret,
        actor=actor,
        access=access,
        workflow_id=workflow_id,
        scopes=scopes,
        kind=kind,
        profile=profile,
    )


@mcp.tool()
def delete_credential(
    credential_id: str,
    workflow_id: str | None = None,
    profile: str | None = None,
) -> dict:
    """Delete a credential from the vault."""
    return tools.delete_credential(
        credential_id=credential_id,
        workflow_id=workflow_id,
        profile=profile,
    )


__all__ = ["create_credential", "delete_credential", "list_credentials"]
