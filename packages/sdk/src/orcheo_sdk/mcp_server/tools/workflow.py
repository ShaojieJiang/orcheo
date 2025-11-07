"""Workflow-related MCP tools."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.mcp_server.config import get_api_client
from orcheo_sdk.services import (
    delete_workflow_data,
    download_workflow_data,
    list_workflows_data,
    run_workflow_data,
    show_workflow_data,
    upload_workflow_data,
)


def list_workflows(
    archived: bool = False,
    profile: str | None = None,
) -> list[dict[str, Any]]:
    """List all workflows in Orcheo."""
    client, _ = get_api_client(profile=profile)
    return list_workflows_data(client, archived=archived)


def show_workflow(
    workflow_id: str,
    profile: str | None = None,
) -> dict[str, Any]:
    """Display details about a workflow."""
    client, _ = get_api_client(profile=profile)
    return show_workflow_data(client, workflow_id)


def run_workflow(
    workflow_id: str,
    inputs: dict[str, Any] | None = None,
    triggered_by: str = "mcp",
    profile: str | None = None,
) -> dict[str, Any]:
    """Trigger a workflow execution using the latest version."""
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
    """Delete a workflow by ID."""
    client, _ = get_api_client(profile=profile)
    return delete_workflow_data(client, workflow_id)


def upload_workflow(
    file_path: str,
    workflow_id: str | None = None,
    workflow_name: str | None = None,
    entrypoint: str | None = None,
    profile: str | None = None,
) -> dict[str, Any]:
    """Upload a workflow from a Python or JSON file."""
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
    """Download workflow configuration."""
    client, _ = get_api_client(profile=profile)
    return download_workflow_data(
        client,
        workflow_id,
        output_path=output_path,
        format_type=format_type,
    )


__all__ = [
    "delete_workflow",
    "download_workflow",
    "list_workflows",
    "run_workflow",
    "show_workflow",
    "upload_workflow",
]
