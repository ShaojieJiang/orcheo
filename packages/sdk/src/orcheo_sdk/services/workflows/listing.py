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
                    raise
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
) -> dict[str, Any]:
    """Return workflow metadata plus optional latest version and runs."""
    if workflow is None:
        workflow = client.get(f"/api/workflows/{workflow_id}")

    if versions is None:
        versions = client.get(f"/api/workflows/{workflow_id}/versions")

    latest_version = None
    if versions:
        latest_version = max(
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
        "latest_version": latest_version,
        "recent_runs": recent_runs,
    }
