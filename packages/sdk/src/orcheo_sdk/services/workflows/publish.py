"""Workflow publish management helpers."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from orcheo_sdk.cli.http import ApiClient


def _build_share_url(base_url: str, workflow_id: str) -> str:
    base = base_url.rstrip("/")
    return f"{base}/chat/{workflow_id}" if workflow_id else base


def _augment_publish_metadata(
    client: ApiClient,
    workflow: Mapping[str, Any],
) -> dict[str, Any]:
    enriched = dict(workflow)
    workflow_id = str(enriched.get("id", "")).strip()
    share_url: str | None = None
    if workflow_id and enriched.get("is_public"):
        share_url = _build_share_url(client.base_url, workflow_id)
    enriched["share_url"] = share_url
    return enriched


def publish_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    require_login: bool = False,
    actor: str = "cli",
) -> dict[str, Any]:
    """Publish a workflow and return publish metadata."""
    payload = client.post(
        f"/api/workflows/{workflow_id}/publish",
        json_body={"require_login": require_login, "actor": actor},
    )
    workflow = _augment_publish_metadata(client, payload.get("workflow", {}))
    share_url = workflow.get("share_url")
    return {
        "workflow": workflow,
        "publish_token": payload.get("publish_token"),
        "message": payload.get("message"),
        "share_url": share_url,
    }


def rotate_publish_token_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str = "cli",
) -> dict[str, Any]:
    """Rotate the publish token for a workflow."""
    payload = client.post(
        f"/api/workflows/{workflow_id}/publish/rotate",
        json_body={"actor": actor},
    )
    workflow = _augment_publish_metadata(client, payload.get("workflow", {}))
    share_url = workflow.get("share_url")
    return {
        "workflow": workflow,
        "publish_token": payload.get("publish_token"),
        "message": payload.get("message"),
        "share_url": share_url,
    }


def unpublish_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str = "cli",
) -> dict[str, Any]:
    """Revoke public access for the workflow."""
    workflow = client.post(
        f"/api/workflows/{workflow_id}/publish/revoke",
        json_body={"actor": actor},
    )
    enriched = _augment_publish_metadata(client, workflow)
    return {
        "workflow": enriched,
        "publish_token": None,
        "message": "Workflow is no longer public.",
        "share_url": enriched.get("share_url"),
    }


__all__ = [
    "publish_workflow_data",
    "rotate_publish_token_data",
    "unpublish_workflow_data",
    "_augment_publish_metadata",
]
