"""Workflow-focused MCP tool registrations."""

from orcheo_sdk.mcp_server import tools
from orcheo_sdk.mcp_server.server import mcp


@mcp.tool()
def list_workflows(
    archived: bool = False,
    profile: str | None = None,
) -> list[dict]:
    """List workflows with optional archived filter."""
    return tools.list_workflows(archived=archived, profile=profile)


@mcp.tool()
def show_workflow(
    workflow_id: str,
    profile: str | None = None,
) -> dict:
    """Display workflow details."""
    return tools.show_workflow(workflow_id=workflow_id, profile=profile)


@mcp.tool()
def run_workflow(
    workflow_id: str,
    inputs: dict | None = None,
    triggered_by: str = "mcp",
    profile: str | None = None,
) -> dict:
    """Trigger a workflow run."""
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
    """Delete a workflow by ID."""
    return tools.delete_workflow(workflow_id=workflow_id, profile=profile)


@mcp.tool()
def upload_workflow(
    file_path: str,
    workflow_id: str | None = None,
    workflow_name: str | None = None,
    entrypoint: str | None = None,
    profile: str | None = None,
) -> dict:
    """Upload a workflow file."""
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
    """Download workflow configuration."""
    return tools.download_workflow(
        workflow_id=workflow_id,
        output_path=output_path,
        format_type=format_type,
        profile=profile,
    )


@mcp.tool()
def publish_workflow(
    workflow_id: str,
    require_login: bool = False,
    profile: str | None = None,
) -> dict:
    """Publish a workflow for ChatKit access."""
    return tools.publish_workflow(
        workflow_id=workflow_id,
        require_login=require_login,
        profile=profile,
    )


@mcp.tool()
def unpublish_workflow(
    workflow_id: str,
    profile: str | None = None,
) -> dict:
    """Revoke public ChatKit access for a workflow."""
    return tools.unpublish_workflow(workflow_id=workflow_id, profile=profile)


__all__ = [
    "delete_workflow",
    "download_workflow",
    "list_workflows",
    "publish_workflow",
    "run_workflow",
    "show_workflow",
    "upload_workflow",
    "unpublish_workflow",
]
