"""Workflow download helpers."""

from __future__ import annotations
from pathlib import Path
from typing import Any
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.http import ApiClient


def download_workflow_data(
    client: ApiClient,
    workflow_id: str,
    output_path: str | Path | None = None,
    format_type: str = "auto",
    target_version: int | None = None,
) -> dict[str, Any]:
    """Download a workflow definition in json or python form.

    Args:
        client: API client for making requests.
        workflow_id: ID of the workflow.
        output_path: Optional path to write the output to.
        format_type: Output format ('auto', 'json', or 'python').
        target_version: Specific version number to download. If None,
            downloads the latest version.

    Returns:
        Dictionary with content and format, or status message if output_path given.
    """
    from orcheo_sdk.cli.workflow import (
        _format_workflow_as_json,
        _format_workflow_as_python,
    )

    workflow = client.get(f"/api/workflows/{workflow_id}")

    if target_version is not None:
        selected_version = client.get(
            f"/api/workflows/{workflow_id}/versions/{target_version}"
        )
    else:
        versions = client.get(f"/api/workflows/{workflow_id}/versions")
        if not versions:
            raise CLIError(f"Workflow '{workflow_id}' has no versions.")
        selected_version = max(versions, key=lambda entry: entry.get("version", 0))

    graph_raw = selected_version.get("graph")
    graph = graph_raw if isinstance(graph_raw, dict) else {}

    resolved_format = format_type.lower()
    if resolved_format == "auto":
        if graph.get("format") == "langgraph-script":
            resolved_format = "python"
        else:
            resolved_format = "json"

    if resolved_format == "json":
        output_content = _format_workflow_as_json(workflow, graph)
    elif resolved_format == "python":
        output_content = _format_workflow_as_python(workflow, graph)
    else:
        raise CLIError(
            f"Unsupported format '{format_type}'. Use 'auto', 'json', or 'python'."
        )

    if output_path:
        try:
            Path(output_path).write_text(output_content, encoding="utf-8")
        except OSError as exc:  # pragma: no cover - filesystem errors
            raise CLIError(
                f"Failed to write workflow output to '{output_path}'."
            ) from exc
        return {
            "status": "success",
            "message": f"Workflow downloaded to '{output_path}'",
            "format": resolved_format,
        }

    return {
        "content": output_content,
        "format": resolved_format,
    }
