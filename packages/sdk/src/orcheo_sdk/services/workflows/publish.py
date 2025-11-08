"""Helpers for workflow publish lifecycle operations."""

from __future__ import annotations

from typing import Any

from orcheo_sdk.cli.http import ApiClient


def _build_share_url(base_url: str, workflow_id: str) -> str:
    """Return the chat share URL for ``workflow_id``."""

    root = base_url.rstrip("/")
    if root.endswith("/api"):
        root = root[: -len("/api")]
    return f"{root}/chat/{workflow_id}"


def _enrich_workflow(base_url: str, workflow: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(workflow)
    workflow_id = str(enriched.get("id")) if enriched.get("id") else None
    if workflow_id and enriched.get("is_public"):
        enriched["share_url"] = _build_share_url(base_url, workflow_id)
    else:
        enriched["share_url"] = None
    return enriched


def publish_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    require_login: bool,
    actor: str,
) -> dict[str, Any]:
    """Publish a workflow and return the enriched response payload."""

    payload: dict[str, Any] = client.post(
        f"/api/workflows/{workflow_id}/publish",
        json_body={"require_login": require_login, "actor": actor},
    )
    workflow = _enrich_workflow(client.base_url, payload["workflow"])
    return {
        "workflow": workflow,
        "publish_token": payload.get("publish_token"),
        "message": payload.get("message"),
        "share_url": workflow.get("share_url"),
    }


def rotate_publish_token_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str,
) -> dict[str, Any]:
    """Rotate a workflow publish token and return enriched payload."""

    payload: dict[str, Any] = client.post(
        f"/api/workflows/{workflow_id}/publish/rotate",
        json_body={"actor": actor},
    )
    workflow = _enrich_workflow(client.base_url, payload["workflow"])
    return {
        "workflow": workflow,
        "publish_token": payload.get("publish_token"),
        "message": payload.get("message"),
        "share_url": workflow.get("share_url"),
    }


def unpublish_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str,
) -> dict[str, Any]:
    """Unpublish a workflow and return the enriched payload."""

    workflow: dict[str, Any] = client.post(
        f"/api/workflows/{workflow_id}/publish/revoke",
        json_body={"actor": actor},
    )
    enriched = _enrich_workflow(client.base_url, workflow)
    return {"workflow": enriched, "share_url": enriched.get("share_url")}


def enrich_workflow_publish_metadata(
    client: ApiClient,
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Return ``workflow`` with derived publish metadata (share URL)."""

    return _enrich_workflow(client.base_url, workflow)


__all__ = [
    "enrich_workflow_publish_metadata",
    "publish_workflow_data",
    "rotate_publish_token_data",
    "unpublish_workflow_data",
]
