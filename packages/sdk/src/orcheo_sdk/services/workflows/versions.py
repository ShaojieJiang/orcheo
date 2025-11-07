"""Workflow version utilities."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.http import ApiClient


def get_latest_workflow_version_data(
    client: ApiClient,
    workflow_id: str,
) -> dict[str, Any]:
    """Return metadata for the latest workflow version."""
    versions = client.get(f"/api/workflows/{workflow_id}/versions")
    if not versions:
        raise CLIError("Workflow has no versions to execute.")

    latest_version = max(versions, key=lambda entry: entry.get("version", 0))
    version_id = latest_version.get("id")
    if not version_id:
        raise CLIError("Latest workflow version is missing an id field.")
    return latest_version
