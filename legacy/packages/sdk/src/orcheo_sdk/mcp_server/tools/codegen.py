"""Workflow code-generation MCP tools."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.mcp_server.config import get_api_client
from orcheo_sdk.services import (
    generate_workflow_scaffold_data,
    generate_workflow_template_data,
)


def generate_workflow_scaffold(
    workflow_id: str,
    actor: str = "mcp",
    profile: str | None = None,
) -> dict[str, Any]:
    """Generate Python code snippet that triggers the workflow."""
    client, _ = get_api_client(profile=profile)
    return generate_workflow_scaffold_data(client, workflow_id, actor=actor)


def generate_workflow_template() -> dict[str, str]:
    """Generate a minimal LangGraph workflow template."""
    return generate_workflow_template_data()


__all__ = ["generate_workflow_scaffold", "generate_workflow_template"]
