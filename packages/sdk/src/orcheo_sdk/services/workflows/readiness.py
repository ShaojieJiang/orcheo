"""Workflow credential readiness helpers."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.http import ApiClient


def get_workflow_credential_readiness_data(
    client: ApiClient,
    workflow_id: str,
) -> dict[str, Any]:
    """Return credential readiness details for a workflow."""
    return client.get(f"/api/workflows/{workflow_id}/credentials/readiness")


__all__ = ["get_workflow_credential_readiness_data"]
