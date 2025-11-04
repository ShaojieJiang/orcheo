"""MCP server entry point for Orcheo CLI.

This module provides a Model Context Protocol (MCP) server that exposes
Orcheo CLI commands as tools, enabling AI agents to interact with Orcheo
workflows programmatically.
"""

from fastmcp import FastMCP
from orcheo_sdk.mcp_server import tools
from orcheo_sdk.mcp_server.config import validate_server_configuration


# Create MCP server instance
mcp = FastMCP("Orcheo CLI")


def create_server() -> FastMCP:
    """Create and configure the Orcheo MCP server.

    Returns:
        Configured FastMCP server instance
    """
    validate_server_configuration()
    return mcp


# ==============================================================================
# Workflow Tools
# ==============================================================================


@mcp.tool()
def list_workflows(
    archived: bool = False,
    profile: str | None = None,
) -> list[dict]:
    """List all workflows in Orcheo.

    Args:
        archived: Include archived workflows in the list
        profile: CLI profile to use for configuration

    Returns:
        List of workflow objects with id, name, slug, and archived status
    """
    return tools.list_workflows(archived=archived, profile=profile)


@mcp.tool()
def show_workflow(
    workflow_id: str,
    profile: str | None = None,
) -> dict:
    """Display details about a workflow including versions and recent runs.

    Args:
        workflow_id: Workflow identifier
        profile: CLI profile to use for configuration

    Returns:
        Dictionary with workflow details, versions, and runs
    """
    return tools.show_workflow(workflow_id=workflow_id, profile=profile)


@mcp.tool()
def run_workflow(
    workflow_id: str,
    inputs: dict | None = None,
    triggered_by: str = "mcp",
    profile: str | None = None,
) -> dict:
    """Trigger a workflow execution using the latest version.

    Note: This uses non-streaming execution. For real-time output streaming,
    use the CLI directly with 'orcheo workflow run --stream'.

    Args:
        workflow_id: Workflow identifier
        inputs: JSON inputs payload (optional)
        triggered_by: Actor triggering the run (default: "mcp")
        profile: CLI profile to use for configuration

    Returns:
        Run details including run ID and status
    """
    return tools.run_workflow(
        workflow_id=workflow_id,
        inputs=inputs,
        triggered_by=triggered_by,
        profile=profile,
    )


@mcp.tool()
def delete_workflow(
    workflow_id: str,
    profile: str | None = None,
) -> dict:
    """Delete a workflow by ID.

    Args:
        workflow_id: Workflow identifier
        profile: CLI profile to use for configuration

    Returns:
        Success message
    """
    return tools.delete_workflow(workflow_id=workflow_id, profile=profile)


@mcp.tool()
def upload_workflow(
    file_path: str,
    workflow_id: str | None = None,
    workflow_name: str | None = None,
    entrypoint: str | None = None,
    profile: str | None = None,
) -> dict:
    """Upload a workflow from a Python or JSON file.

    Supports two Python formats:
    1. SDK Workflow: File defines a 'workflow' variable with Workflow instance
    2. LangGraph script: Raw LangGraph code (auto-detected if no 'workflow' var)

    For JSON files, must contain valid workflow config with 'name' and 'graph'.

    Args:
        file_path: Path to workflow file (.py or .json)
        workflow_id: Workflow ID for updates (creates new if omitted)
        workflow_name: Optional workflow name override
        entrypoint: Optional entrypoint function/variable for LangGraph scripts
        profile: CLI profile to use for configuration

    Returns:
        Created or updated workflow object
    """
    return tools.upload_workflow(
        file_path=file_path,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        entrypoint=entrypoint,
        profile=profile,
    )


@mcp.tool()
def download_workflow(
    workflow_id: str,
    output_path: str | None = None,
    format_type: str = "auto",
    profile: str | None = None,
) -> dict:
    """Download workflow configuration.

    Supports downloading as JSON, Python code, or auto (auto-detects format).
    When format is 'auto' (default), LangGraph scripts download as Python,
    others as JSON.

    Args:
        workflow_id: Workflow identifier
        output_path: Output file path (returns content if None)
        format_type: Output format - 'auto', 'json', or 'python' (default: 'auto')
        profile: CLI profile to use for configuration

    Returns:
        Dict with 'content' key containing the workflow code/config
        (if no output_path), or success message (if output_path provided)
    """
    return tools.download_workflow(
        workflow_id=workflow_id,
        output_path=output_path,
        format_type=format_type,
        profile=profile,
    )


# ==============================================================================
# Node Tools
# ==============================================================================


@mcp.tool()
def list_nodes(tag: str | None = None) -> list[dict]:
    """List registered nodes with metadata.

    Args:
        tag: Filter nodes by category or name keyword (optional)

    Returns:
        List of node metadata objects with name, category, and description
    """
    return tools.list_nodes(tag=tag)


@mcp.tool()
def show_node(name: str) -> dict:
    """Display metadata and schema information for a node.

    Args:
        name: Node name as registered in the catalog

    Returns:
        Dictionary with node metadata and Pydantic schema
    """
    return tools.show_node(name=name)


# ==============================================================================
# Credential Tools
# ==============================================================================


@mcp.tool()
def list_credentials(
    workflow_id: str | None = None,
    profile: str | None = None,
) -> list[dict]:
    """List credentials visible to the caller.

    Args:
        workflow_id: Filter by workflow identifier (optional)
        profile: CLI profile to use for configuration

    Returns:
        List of credential objects
    """
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
    """Create a credential via the vault API.

    Args:
        name: Credential name
        provider: Credential provider identifier
        secret: Credential secret value
        actor: Actor creating the credential (default: "mcp")
        access: Access level - 'private', 'shared', or 'public' (default: 'private')
        workflow_id: Optional workflow association
        scopes: Optional list of scopes
        kind: Credential kind (default: 'secret')
        profile: CLI profile to use for configuration

    Returns:
        Created credential object
    """
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
    """Delete a credential from the vault.

    Args:
        credential_id: Credential identifier
        workflow_id: Optional workflow association
        profile: CLI profile to use for configuration

    Returns:
        Success message
    """
    return tools.delete_credential(
        credential_id=credential_id,
        workflow_id=workflow_id,
        profile=profile,
    )


@mcp.tool()
def get_credential_reference(name: str) -> dict:
    """Get the credential reference string for use in nodes or workflows.

    Args:
        name: Credential name

    Returns:
        Dictionary with reference string like '[[credential_name]]'
    """
    return tools.get_credential_reference(name=name)


# ==============================================================================
# Code Generation Tools
# ==============================================================================


@mcp.tool()
def generate_workflow_scaffold(
    workflow_id: str,
    actor: str = "mcp",
    profile: str | None = None,
) -> dict:
    """Generate Python code snippet that triggers a workflow.

    Args:
        workflow_id: Workflow identifier
        actor: Actor used in the snippet (default: "mcp")
        profile: CLI profile to use for configuration

    Returns:
        Dictionary with Python code snippet and workflow metadata
    """
    return tools.generate_workflow_scaffold(
        workflow_id=workflow_id,
        actor=actor,
        profile=profile,
    )


@mcp.tool()
def generate_workflow_template() -> dict:
    """Generate a minimal LangGraph workflow template.

    Returns:
        Dictionary with template Python code that can be used as
        a starting point for building custom Orcheo workflows
    """
    return tools.generate_workflow_template()


# ==============================================================================
# Agent Tool Discovery Tools
# ==============================================================================


@mcp.tool()
def list_agent_tools(category: str | None = None) -> list[dict]:
    """List registered agent tools with metadata.

    Args:
        category: Filter tools by category or name keyword (optional)

    Returns:
        List of agent tool metadata objects
    """
    return tools.list_agent_tools(category=category)


@mcp.tool()
def show_agent_tool(name: str) -> dict:
    """Display metadata and schema information for an agent tool.

    Args:
        name: Tool name as registered in the catalog

    Returns:
        Dictionary with tool metadata and schema
    """
    return tools.show_agent_tool(name=name)


# ==============================================================================
# Service Token Tools
# ==============================================================================


@mcp.tool()
def list_service_tokens(profile: str | None = None) -> dict:
    """List all service tokens.

    Args:
        profile: CLI profile to use for configuration

    Returns:
        Dictionary with tokens list and total count
    """
    return tools.list_service_tokens(profile=profile)


@mcp.tool()
def show_service_token(
    token_id: str,
    profile: str | None = None,
) -> dict:
    """Display details for a specific service token.

    Args:
        token_id: Token identifier
        profile: CLI profile to use for configuration

    Returns:
        Service token details
    """
    return tools.show_service_token(token_id=token_id, profile=profile)


@mcp.tool()
def create_service_token(
    identifier: str | None = None,
    scopes: list[str] | None = None,
    workspace_ids: list[str] | None = None,
    expires_in_seconds: int | None = None,
    profile: str | None = None,
) -> dict:
    """Create a new service token.

    The token secret is displayed once and cannot be retrieved later.
    Store it securely.

    Args:
        identifier: Optional identifier for the token
        scopes: Optional list of scopes to grant
        workspace_ids: Optional list of workspace IDs the token can access
        expires_in_seconds: Optional expiration time in seconds (minimum 60)
        profile: CLI profile to use for configuration

    Returns:
        Created token with identifier and secret
    """
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
    """Rotate a service token, generating a new secret.

    The old token remains valid during the overlap period.

    Args:
        token_id: Token identifier to rotate
        overlap_seconds: Grace period in seconds where both tokens are valid
            (default: 300)
        expires_in_seconds: Optional expiration time for new token in seconds
            (minimum 60)
        profile: CLI profile to use for configuration

    Returns:
        New token with identifier and secret
    """
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
    """Revoke a service token immediately.

    Args:
        token_id: Token identifier to revoke
        reason: Reason for revocation
        profile: CLI profile to use for configuration

    Returns:
        Success message
    """
    return tools.revoke_service_token(
        token_id=token_id,
        reason=reason,
        profile=profile,
    )


# ==============================================================================
# Entry Point
# ==============================================================================


def main() -> None:
    """Run the MCP server.

    This is the main entry point for the orcheo-mcp command.
    """
    validate_server_configuration()
    mcp.run()


if __name__ == "__main__":  # pragma: no cover
    main()
