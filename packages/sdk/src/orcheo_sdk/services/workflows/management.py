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
