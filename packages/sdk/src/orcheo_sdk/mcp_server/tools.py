"""MCP tool implementations that wrap Orcheo service layer.

Each tool wraps the service layer functions, making Orcheo functionality
available to AI agents via the Model Context Protocol.
"""

from __future__ import annotations
import logging
from functools import lru_cache
from importlib import import_module, util
from typing import Any
from orcheo_sdk.mcp_server.config import get_api_client
from orcheo_sdk.services import (
    create_credential_data,
    create_service_token_data,
    delete_credential_data,
    delete_workflow_data,
    download_workflow_data,
    generate_workflow_scaffold_data,
    generate_workflow_template_data,
    get_credential_reference_data,
    list_credentials_data,
    list_nodes_data,
    list_service_tokens_data,
    list_workflows_data,
    revoke_service_token_data,
    rotate_service_token_data,
    run_workflow_data,
    show_node_data,
    show_service_token_data,
    show_workflow_data,
    upload_workflow_data,
)


# ==============================================================================
# Module setup
# ==============================================================================


logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _ensure_agent_tools_registered() -> None:
    """Import agent tool modules so they register with the catalog."""
    module_name = "orcheo.nodes.agent_tools.tools"

    spec = util.find_spec(module_name)
    if spec is None:
        logger.warning(
            "Optional agent tools module '%s' could not be found. "
            "Install orcheo agent tool plugins to enable additional tools.",
            module_name,
        )
        return

    try:
        import_module(module_name)
    except Exception:  # pragma: no cover - defensive logging
        logger.exception(
            "Failed to import optional agent tools module '%s'.",
            module_name,
        )


# ==============================================================================
# Workflow Tools
# ==============================================================================


def list_workflows(
    archived: bool = False,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """List all workflows in Orcheo.

    Args:
        archived: Include archived workflows in the list
        profile: CLI profile to use for configuration

    Returns:
        List of workflow objects with id, name, slug, and archived status
    """
    client, _ = get_api_client(profile=profile)
    return list_workflows_data(client, archived=archived)


def show_workflow(
    workflow_id: str,
    profile: str | None = None,
) -> dict[str, Any]:
    """Display details about a workflow including versions and recent runs.

    Args:
        workflow_id: Workflow identifier
        profile: CLI profile to use for configuration

    Returns:
        Dictionary with workflow details, versions, and runs
    """
    client, _ = get_api_client(profile=profile)
    return show_workflow_data(client, workflow_id)


def run_workflow(
    workflow_id: str,
    inputs: dict[str, Any] | None = None,
    triggered_by: str = "mcp",
    profile: str | None = None,
) -> dict[str, Any]:
    """Trigger a workflow execution using the latest version.

    Note: This uses non-streaming execution. For streaming, use the CLI directly.

    Args:
        workflow_id: Workflow identifier
        inputs: JSON inputs payload
        triggered_by: Actor triggering the run
        profile: CLI profile to use for configuration

    Returns:
        Run details including run ID and status
    """
    client, settings = get_api_client(profile=profile)
    return run_workflow_data(
        client,
        workflow_id,
        settings.service_token,
        inputs=inputs,
        triggered_by=triggered_by,
    )


def delete_workflow(
    workflow_id: str,
    profile: str | None = None,
) -> dict[str, str]:
    """Delete a workflow by ID.

    Args:
        workflow_id: Workflow identifier
        profile: CLI profile to use for configuration

    Returns:
        Success message
    """
    client, _ = get_api_client(profile=profile)
    return delete_workflow_data(client, workflow_id)


def upload_workflow(
    file_path: str,
    workflow_id: str | None = None,
    workflow_name: str | None = None,
    entrypoint: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
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
    client, _ = get_api_client(profile=profile)
    return upload_workflow_data(
        client,
        file_path,
        workflow_id=workflow_id,
        workflow_name=workflow_name,
        entrypoint=entrypoint,
    )


def download_workflow(
    workflow_id: str,
    output_path: str | None = None,
    format_type: str = "auto",
    profile: str | None = None,
) -> dict[str, Any]:
    """Download workflow configuration.

    Supports downloading as JSON, Python code, or auto (auto-detects format).
    When format is 'auto' (default), LangGraph scripts download as Python,
    others as JSON.

    Args:
        workflow_id: Workflow identifier
        output_path: Output file path (returns content if None)
        format_type: Output format (auto, json, or python)
        profile: CLI profile to use for configuration

    Returns:
        Dict with 'content' key containing the workflow code/config,
        and 'format' key indicating the format used
    """
    client, _ = get_api_client(profile=profile)
    return download_workflow_data(
        client,
        workflow_id,
        output_path=output_path,
        format_type=format_type,
    )


# ==============================================================================
# Node Tools
# ==============================================================================


def list_nodes(tag: str | None = None) -> list[dict[str, Any]]:
    """List registered nodes with metadata.

    Args:
        tag: Filter nodes by category keyword

    Returns:
        List of node metadata objects
    """
    return list_nodes_data(tag=tag)


def show_node(name: str) -> dict[str, Any]:
    """Display metadata and schema information for a node.

    Args:
        name: Node name as registered in the catalog

    Returns:
        Dictionary with node metadata and Pydantic schema
    """
    return show_node_data(name)


# ==============================================================================
# Credential Tools
# ==============================================================================


def list_credentials(
    workflow_id: str | None = None,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """List credentials visible to the caller.

    Args:
        workflow_id: Filter by workflow identifier
        profile: CLI profile to use for configuration

    Returns:
        List of credential objects
    """
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
    """Create a credential via the vault API.

    Args:
        name: Credential name
        provider: Credential provider identifier
        secret: Credential secret value
        actor: Actor creating the credential
        access: Access level (private/shared/public)
        workflow_id: Optional workflow association
        scopes: Optional list of scopes
        kind: Credential kind
        profile: CLI profile to use for configuration

    Returns:
        Created credential object
    """
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
    """Delete a credential from the vault.

    Args:
        credential_id: Credential identifier
        workflow_id: Optional workflow association
        profile: CLI profile to use for configuration

    Returns:
        Success message
    """
    client, _ = get_api_client(profile=profile)
    return delete_credential_data(client, credential_id, workflow_id=workflow_id)


def get_credential_reference(name: str) -> dict[str, str]:
    """Get the credential reference string for use in nodes or workflows.

    Args:
        name: Credential name

    Returns:
        Dictionary with reference string
    """
    return get_credential_reference_data(name)


# ==============================================================================
# Code Generation Tools
# ==============================================================================


def generate_workflow_scaffold(
    workflow_id: str,
    actor: str = "mcp",
    profile: str | None = None,
) -> dict[str, Any]:
    """Generate Python code snippet that triggers the workflow.

    Args:
        workflow_id: Workflow identifier
        actor: Actor used in the snippet
        profile: CLI profile to use for configuration

    Returns:
        Dictionary with Python code snippet and workflow metadata
    """
    client, _ = get_api_client(profile=profile)
    return generate_workflow_scaffold_data(client, workflow_id, actor=actor)


def generate_workflow_template() -> dict[str, str]:
    """Generate a minimal LangGraph workflow template.

    Returns:
        Dictionary with template Python code
    """
    return generate_workflow_template_data()


# ==============================================================================
# Agent Tool Discovery Tools
# ==============================================================================


def list_agent_tools(category: str | None = None) -> list[dict[str, Any]]:
    """List registered agent tools with metadata.

    Args:
        category: Filter tools by category keyword

    Returns:
        List of agent tool metadata objects
    """
    from orcheo.nodes.agent_tools.registry import tool_registry

    _ensure_agent_tools_registered()

    entries = tool_registry.list_metadata()

    if category:
        lowered = category.lower()
        entries = [
            item
            for item in entries
            if lowered in item.category.lower() or lowered in item.name.lower()
        ]

    return [
        {
            "name": item.name,
            "category": item.category,
            "description": item.description,
        }
        for item in entries
    ]


def show_agent_tool(name: str) -> dict[str, Any]:
    """Display metadata and schema information for an agent tool.

    Args:
        name: Tool name as registered in the catalog

    Returns:
        Dictionary with tool metadata and schema
    """
    from orcheo.nodes.agent_tools.registry import tool_registry
    from orcheo_sdk.cli.errors import CLIError

    _ensure_agent_tools_registered()

    metadata = tool_registry.get_metadata(name)
    tool = tool_registry.get_tool(name)

    if metadata is None or tool is None:
        raise CLIError(f"Agent tool '{name}' is not registered.")

    result: dict[str, Any] = {
        "name": metadata.name,
        "category": metadata.category,
        "description": metadata.description,
    }

    # Extract schema
    schema_data: dict[str, Any] = {}
    if hasattr(tool, "args_schema") and tool.args_schema is not None:
        if hasattr(tool.args_schema, "model_json_schema"):
            schema_data = tool.args_schema.model_json_schema()
    elif hasattr(tool, "model_json_schema"):
        schema_data = tool.model_json_schema()

    if schema_data:
        result["schema"] = schema_data

    return result


# ==============================================================================
# Service Token Tools
# ==============================================================================


def list_service_tokens(
    profile: str | None = None,
) -> dict[str, Any]:
    """List all service tokens.

    Args:
        profile: CLI profile to use for configuration

    Returns:
        Dictionary with tokens list and total count
    """
    client, _ = get_api_client(profile=profile)
    return list_service_tokens_data(client)


def show_service_token(
    token_id: str,
    profile: str | None = None,
) -> dict[str, Any]:
    """Display details for a specific service token.

    Args:
        token_id: Token identifier
        profile: CLI profile to use for configuration

    Returns:
        Service token details
    """
    client, _ = get_api_client(profile=profile)
    return show_service_token_data(client, token_id)


def create_service_token(
    identifier: str | None = None,
    scopes: list[str] | None = None,
    workspace_ids: list[str] | None = None,
    expires_in_seconds: int | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
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
    """Revoke a service token immediately.

    Args:
        token_id: Token identifier to revoke
        reason: Reason for revocation
        profile: CLI profile to use for configuration

    Returns:
        Success message
    """
    client, _ = get_api_client(profile=profile)
    return revoke_service_token_data(client, token_id, reason)
