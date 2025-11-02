"""Workflow service operations.

Pure business logic for workflow operations, shared by CLI and MCP interfaces.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.http import ApiClient


def list_workflows_data(
    client: ApiClient,
    archived: bool = False,
) -> list[dict[str, Any]]:
    """Get list of workflows.

    Args:
        client: API client instance
        archived: Include archived workflows

    Returns:
        List of workflow objects
    """
    url = "/api/workflows"
    if archived:
        url += "?include_archived=true"
    return client.get(url)


def show_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    include_runs: bool = True,
    workflow: dict[str, Any] | None = None,
    versions: list[dict[str, Any]] | None = None,
    runs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Get workflow details including versions and runs.

    Args:
        client: API client instance
        workflow_id: Workflow identifier
        include_runs: Include recent runs in the response
        workflow: Optional pre-fetched workflow metadata
        versions: Optional pre-fetched versions list
        runs: Optional pre-fetched runs list

    Returns:
        Dictionary with workflow, latest_version, and recent_runs
    """
    # Get workflow details
    if workflow is None:
        workflow = client.get(f"/api/workflows/{workflow_id}")

    # Get versions
    if versions is None:
        versions = client.get(f"/api/workflows/{workflow_id}/versions")
    latest_version = None
    if versions:
        latest_version = max(
            versions,
            key=lambda entry: entry.get("version", 0),
        )

    # Get runs
    recent_runs = []
    if include_runs:
        if runs is None:
            runs = client.get(f"/api/workflows/{workflow_id}/runs")
        if runs:
            recent_runs = sorted(
                runs,
                key=lambda item: item.get("created_at", ""),
                reverse=True,
            )[:5]

    return {
        "workflow": workflow,
        "latest_version": latest_version,
        "recent_runs": recent_runs,
    }


def get_latest_workflow_version_data(
    client: ApiClient,
    workflow_id: str,
) -> dict[str, Any]:
    """Return the latest workflow version metadata.

    Args:
        client: API client instance
        workflow_id: Workflow identifier

    Returns:
        Latest workflow version object

    Raises:
        CLIError: If no versions exist or latest version lacks an id field
    """
    versions = client.get(f"/api/workflows/{workflow_id}/versions")
    if not versions:
        raise CLIError("Workflow has no versions to execute.")

    latest_version = max(versions, key=lambda entry: entry.get("version", 0))
    version_id = latest_version.get("id")
    if not version_id:
        raise CLIError("Latest workflow version is missing an id field.")
    return latest_version


def run_workflow_data(
    client: ApiClient,
    workflow_id: str,
    service_token: str | None,
    inputs: dict[str, Any] | None = None,
    triggered_by: str = "api",
) -> dict[str, Any]:
    """Trigger workflow execution.

    Args:
        client: API client instance
        workflow_id: Workflow identifier
        service_token: Service token for authentication
        inputs: Input data for workflow
        triggered_by: Actor triggering the run

    Returns:
        Run details including run ID and status

    Raises:
        CLIError: If workflow has no versions
    """
    from orcheo_sdk.client import HttpWorkflowExecutor, OrcheoClient

    # Get latest version
    latest_version = get_latest_workflow_version_data(client, workflow_id)
    version_id = latest_version["id"]

    # Execute workflow
    orcheo_client = OrcheoClient(base_url=client.base_url)
    executor = HttpWorkflowExecutor(
        orcheo_client,
        auth_token=service_token,
        timeout=30.0,
    )

    result = executor.trigger_run(
        workflow_id,
        workflow_version_id=version_id,
        triggered_by=triggered_by,
        inputs=inputs or {},
    )

    return result


def delete_workflow_data(
    client: ApiClient,
    workflow_id: str,
) -> dict[str, str]:
    """Delete a workflow.

    Args:
        client: API client instance
        workflow_id: Workflow identifier

    Returns:
        Success message
    """
    response = client.delete(f"/api/workflows/{workflow_id}")
    if response and "message" in response:
        return {"status": "success", "message": response["message"]}
    return {"status": "success", "message": f"Workflow '{workflow_id}' deleted"}


def upload_workflow_data(
    client: ApiClient,
    file_path: str | Path,
    workflow_id: str | None = None,
    workflow_name: str | None = None,
    entrypoint: str | None = None,
    console: Any | None = None,
) -> dict[str, Any]:
    """Upload workflow from file.

    Args:
        client: API client instance
        file_path: Path to workflow file
        workflow_id: Optional workflow ID for updates
        workflow_name: Optional workflow name override
        entrypoint: Optional LangGraph entrypoint override
        console: Optional console for status output

    Returns:
        Created or updated workflow object

    Raises:
        CLIError: If file format is unsupported or invalid
    """
    from orcheo_sdk.cli.workflow import (
        _load_workflow_from_json,
        _load_workflow_from_python,
        _normalize_workflow_name,
        _upload_langgraph_script,
        _validate_local_path,
    )

    # Create minimal state for upload functions
    class MinimalState:
        def __init__(self, client_obj: Any, console_obj: Any | None) -> None:
            self.client = client_obj
            self.console = console_obj or _FakeConsole()

    class _FakeConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            pass  # Suppress output

    state = MinimalState(client, console)

    requested_name = _normalize_workflow_name(workflow_name)
    path_obj = _validate_local_path(file_path, description="workflow")

    # Load workflow based on file type
    file_extension = path_obj.suffix.lower()
    if file_extension == ".py":
        workflow_config = _load_workflow_from_python(path_obj)
    elif file_extension == ".json":
        workflow_config = _load_workflow_from_json(path_obj)
    else:
        raise CLIError(
            f"Unsupported file type '{file_extension}'. Use .py or .json files."
        )

    # Handle LangGraph scripts
    is_langgraph_script = workflow_config.get("_type") == "langgraph_script"
    if is_langgraph_script:
        if entrypoint:
            workflow_config["entrypoint"] = entrypoint
        result = _upload_langgraph_script(
            state,  # type: ignore[arg-type]
            workflow_config,
            workflow_id,
            path_obj,
            requested_name,
        )
    else:
        if requested_name:
            workflow_config["name"] = requested_name
        if workflow_id:
            url = f"/api/workflows/{workflow_id}"
        else:
            url = "/api/workflows"
        result = client.post(url, json_body=workflow_config)

    return result


def download_workflow_data(
    client: ApiClient,
    workflow_id: str,
    output_path: str | Path | None = None,
    format_type: str = "auto",
) -> dict[str, Any]:
    """Download workflow configuration.

    Args:
        client: API client instance
        workflow_id: Workflow identifier
        output_path: Optional output file path
        format_type: Output format (auto, json, or python)

    Returns:
        Dict with content and format, or success message if output_path provided

    Raises:
        CLIError: If workflow has no versions or format is invalid
    """
    from orcheo_sdk.cli.workflow import (
        _format_workflow_as_json,
        _format_workflow_as_python,
    )

    # Get workflow and versions
    workflow = client.get(f"/api/workflows/{workflow_id}")
    versions = client.get(f"/api/workflows/{workflow_id}/versions")

    if not versions:
        raise CLIError(f"Workflow '{workflow_id}' has no versions.")

    latest_version = max(versions, key=lambda entry: entry.get("version", 0))
    graph_raw = latest_version.get("graph")
    graph = graph_raw if isinstance(graph_raw, dict) else {}

    # Auto-detect format
    resolved_format = format_type.lower()
    if resolved_format == "auto":
        if graph.get("format") == "langgraph-script":
            resolved_format = "python"
        else:
            resolved_format = "json"

    # Format output
    if resolved_format == "json":
        output_content = _format_workflow_as_json(workflow, graph)
    elif resolved_format == "python":
        output_content = _format_workflow_as_python(workflow, graph)
    else:
        raise CLIError(
            f"Unsupported format '{format_type}'. Use 'auto', 'json', or 'python'."
        )

    # Write to file if path provided
    if output_path:
        Path(output_path).write_text(output_content, encoding="utf-8")
        return {
            "status": "success",
            "message": f"Workflow downloaded to '{output_path}'",
            "format": resolved_format,
        }

    return {
        "content": output_content,
        "format": resolved_format,
    }
