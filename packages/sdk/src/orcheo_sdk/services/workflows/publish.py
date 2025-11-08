"""Workflow publish management helpers."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from orcheo_sdk.cli.http import ApiClient


def _build_share_url(
    canvas_base_url: str | None,
    workflow_id: str,
    *,
    is_public: bool,
) -> str | None:
    """Return the share URL when the workflow is public and base URL is known."""
    if not is_public:
        return None
    if not canvas_base_url:
        return None
    base = canvas_base_url.rstrip("/")
    if not base:
        return None
    return f"{base}/chat/{workflow_id}"


def enrich_workflow_publish_metadata(
    workflow: Mapping[str, Any],
    canvas_base_url: str | None,
) -> dict[str, Any]:
    """Return a copy of ``workflow`` enriched with share URL metadata."""
    data = dict(workflow)
    workflow_id = str(data.get("id") or "").strip()
    share_url = None
    if workflow_id:
        share_url = _build_share_url(
            canvas_base_url,
            workflow_id,
            is_public=bool(data.get("is_public")),
        )
    data["share_url"] = share_url
    return data


def publish_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    require_login: bool = False,
    actor: str | None = None,
    canvas_base_url: str | None = None,
) -> dict[str, Any]:
    """Publish a workflow and enrich the response payload."""
    payload: dict[str, Any] = {"require_login": require_login}
    if actor:
        payload["actor"] = actor
    response: dict[str, Any] = client.post(
        f"/api/workflows/{workflow_id}/publish",
        json_body=payload,
    )
    workflow = response.get("workflow")
    if isinstance(workflow, Mapping):
        enriched = enrich_workflow_publish_metadata(workflow, canvas_base_url)
        response["workflow"] = enriched
        response.setdefault("share_url", enriched.get("share_url"))
    return response


def rotate_publish_token_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str | None = None,
    canvas_base_url: str | None = None,
) -> dict[str, Any]:
    """Rotate the publish token for a workflow."""
    payload: dict[str, Any] = {}
    if actor:
        payload["actor"] = actor
    response: dict[str, Any] = client.post(
        f"/api/workflows/{workflow_id}/publish/rotate",
        json_body=payload,
    )
    workflow = response.get("workflow")
    if isinstance(workflow, Mapping):
        enriched = enrich_workflow_publish_metadata(workflow, canvas_base_url)
        response["workflow"] = enriched
        response.setdefault("share_url", enriched.get("share_url"))
    return response


def unpublish_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str | None = None,
    canvas_base_url: str | None = None,
) -> dict[str, Any]:
    """Revoke public access to a workflow."""
    payload: dict[str, Any] = {}
    if actor:
        payload["actor"] = actor
    workflow: dict[str, Any] = client.post(
        f"/api/workflows/{workflow_id}/publish/revoke",
        json_body=payload,
    )
    enriched = enrich_workflow_publish_metadata(workflow, canvas_base_url)
    return {"workflow": enriched, "share_url": enriched.get("share_url")}


__all__ = [
    "publish_workflow_data",
    "rotate_publish_token_data",
    "unpublish_workflow_data",
    "enrich_workflow_publish_metadata",
]
