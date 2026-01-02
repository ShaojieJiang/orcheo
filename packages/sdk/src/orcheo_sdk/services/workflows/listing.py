"""Workflow listing and detail helpers."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.errors import APICallError
from orcheo_sdk.cli.http import ApiClient
from orcheo_sdk.services.workflows.publish import enrich_workflow_publish_metadata


def list_workflows_data(
    client: ApiClient,
    archived: bool = False,
) -> list[dict[str, Any]]:
    """Return workflows optionally including archived entries."""
    url = "/api/workflows"
    if archived:
        url += "?include_archived=true"
    payload = client.get(url)
    enriched = []
    for item in payload:
        enriched_item = enrich_workflow_publish_metadata(client, item)
        # Check if workflow has cron trigger configured
        workflow_id = enriched_item.get("id")
        if workflow_id:
            try:
                cron_url = f"/api/workflows/{workflow_id}/triggers/cron/config"
                client.get(cron_url)
                enriched_item["is_scheduled"] = True
            except APICallError as exc:
                if exc.status_code == 404:
                    enriched_item["is_scheduled"] = False
                else:
                    raise  # pragma: no cover - defensive
        else:
            enriched_item["is_scheduled"] = False
        enriched.append(enriched_item)
    return enriched


def show_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    include_runs: bool = True,
    workflow: dict[str, Any] | None = None,
    versions: list[dict[str, Any]] | None = None,
    runs: list[dict[str, Any]] | None = None,
    target_version: int | None = None,
) -> dict[str, Any]:
    """Return workflow metadata plus optional version and runs.

    Args:
        client: API client for making requests.
        workflow_id: ID of the workflow.
        include_runs: Whether to include recent runs.
        workflow: Pre-fetched workflow data (optional).
        versions: Pre-fetched versions list (optional).
        runs: Pre-fetched runs list (optional).
        target_version: Specific version number to retrieve. If None,
            returns the latest version.

    Returns:
        Dictionary containing workflow details, selected version, and recent runs.
    """
    if workflow is None:
        workflow = client.get(f"/api/workflows/{workflow_id}")

    selected_version: dict[str, Any] | None = None
    if target_version is not None:
        selected_version = client.get(
            f"/api/workflows/{workflow_id}/versions/{target_version}"
        )
    else:
        if versions is None:
            versions = client.get(f"/api/workflows/{workflow_id}/versions")
        if versions:
            selected_version = max(
                versions,
                key=lambda entry: entry.get("version", 0),
            )

    recent_runs: list[dict[str, Any]] = []
    if include_runs:
        if runs is None:
            runs = client.get(f"/api/workflows/{workflow_id}/runs")
        if runs:
            recent_runs = sorted(
                runs,
                key=lambda item: item.get("created_at", ""),
                reverse=True,
            )[:5]

    enriched_workflow = enrich_workflow_publish_metadata(client, workflow)

    return {
        "workflow": enriched_workflow,
        "selected_version": selected_version,
        "recent_runs": recent_runs,
    }
