"""Workflow publish management helpers."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from orcheo_sdk.cli.http import ApiClient


@dataclass(slots=True)
class PublishSummary:
    """Normalized publish metadata for CLI and MCP consumers."""

    status: str
    require_login: bool
    share_url: str | None
    published_at: str | None
    publish_token_rotated_at: str | None
    published_by: str | None


def _share_url(base_url: str, workflow_id: str) -> str:
    """Build the public share URL for ``workflow_id``."""
    normalized = base_url.rstrip("/")
    return f"{normalized}/chat/{workflow_id}"


def _publish_summary(client: ApiClient, workflow: dict[str, Any]) -> PublishSummary:
    """Return publish summary metadata for ``workflow``."""
    is_public = bool(workflow.get("is_public"))
    share_url = None
    if is_public and workflow.get("id"):
        share_url = _share_url(client.base_url, str(workflow["id"]))

    return PublishSummary(
        status="public" if is_public else "private",
        require_login=bool(workflow.get("require_login")),
        share_url=share_url,
        published_at=workflow.get("published_at"),
        publish_token_rotated_at=workflow.get("publish_token_rotated_at"),
        published_by=workflow.get("published_by"),
    )


def enrich_workflow_publish_data(
    client: ApiClient,
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Return ``workflow`` with attached publish summary metadata."""
    enriched = dict(workflow)
    summary = _publish_summary(client, workflow)
    enriched["publish_summary"] = {
        "status": summary.status,
        "require_login": summary.require_login,
        "share_url": summary.share_url,
        "published_at": summary.published_at,
        "publish_token_rotated_at": summary.publish_token_rotated_at,
        "published_by": summary.published_by,
    }
    return enriched


def publish_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    require_login: bool = False,
    actor: str = "cli",
) -> dict[str, Any]:
    """Publish ``workflow_id`` and return normalized response payload."""
    payload = client.post(
        f"/api/workflows/{workflow_id}/publish",
        json_body={"require_login": require_login, "actor": actor},
    )
    workflow = enrich_workflow_publish_data(client, payload["workflow"])
    summary = workflow["publish_summary"]
    return {
        "workflow": workflow,
        "publish_token": payload.get("publish_token"),
        "message": payload.get("message"),
        "publish_summary": summary,
    }


def rotate_publish_token_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str = "cli",
) -> dict[str, Any]:
    """Rotate publish token for ``workflow_id`` and return payload."""
    payload = client.post(
        f"/api/workflows/{workflow_id}/publish/rotate",
        json_body={"actor": actor},
    )
    workflow = enrich_workflow_publish_data(client, payload["workflow"])
    summary = workflow["publish_summary"]
    return {
        "workflow": workflow,
        "publish_token": payload.get("publish_token"),
        "message": payload.get("message"),
        "publish_summary": summary,
    }


def revoke_workflow_publish_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str = "cli",
) -> dict[str, Any]:
    """Revoke publish access for ``workflow_id``."""
    workflow = client.post(
        f"/api/workflows/{workflow_id}/publish/revoke",
        json_body={"actor": actor},
    )
    enriched = enrich_workflow_publish_data(client, workflow)
    return {
        "workflow": enriched,
        "publish_summary": enriched["publish_summary"],
    }


__all__ = [
    "enrich_workflow_publish_data",
    "publish_workflow_data",
    "rotate_publish_token_data",
    "revoke_workflow_publish_data",
]
