"""Workflow management helpers."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.http import ApiClient


def delete_workflow_data(
    client: ApiClient,
    workflow_id: str,
) -> dict[str, str]:
    """Delete a workflow and return a consistent success payload."""
    response: dict[str, Any] | None = client.delete(f"/api/workflows/{workflow_id}")
    if response and "message" in response:
        return {"status": "success", "message": response["message"]}
    return {
        "status": "success",
        "message": f"Workflow '{workflow_id}' deleted",
    }


def update_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    name: str | None = None,
    handle: str | None = None,
    description: str | None = None,
    actor: str = "cli",
) -> dict[str, Any]:
    """Update workflow metadata and return the backend payload."""
    payload: dict[str, Any] = {"actor": actor}
    if name is not None:
        payload["name"] = name
    if handle is not None:
        payload["handle"] = handle
    if description is not None:
        payload["description"] = description
    return client.put(f"/api/workflows/{workflow_id}", json_body=payload)
