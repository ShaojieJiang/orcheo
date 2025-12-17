"""Workflow execution helpers."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.http import ApiClient
from orcheo_sdk.services.workflows.versions import get_latest_workflow_version_data


def run_workflow_data(
    client: ApiClient,
    workflow_id: str,
    service_token: str | None,
    inputs: dict[str, Any] | None = None,
    triggered_by: str = "api",
    runnable_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Trigger workflow execution using the latest version."""
    from orcheo_sdk.client import HttpWorkflowExecutor, OrcheoClient

    latest_version = get_latest_workflow_version_data(client, workflow_id)
    version_id = latest_version["id"]

    if not version_id:
        raise CLIError("Latest workflow version is missing an id field.")

    orcheo_client = OrcheoClient(base_url=client.base_url)
    executor = HttpWorkflowExecutor(
        orcheo_client,
        auth_token=service_token,
        timeout=30.0,
    )

    return executor.trigger_run(
        workflow_id,
        workflow_version_id=version_id,
        triggered_by=triggered_by,
        inputs=inputs or {},
        runnable_config=runnable_config,
    )
