"""Helpers for workflow publish lifecycle operations."""

from __future__ import annotations
import re
from typing import Any
from orcheo_sdk.cli.http import ApiClient


_API_SUFFIX_PATTERN = re.compile(r"(/api)(/v[0-9]+)?$")


def _build_share_url(
    base_url: str, workflow_id: str, *, public_base_url: str | None = None
) -> str:
    """Return the chat share URL for ``workflow_id``."""
    origin = (public_base_url or base_url).rstrip("/")
    if public_base_url:
        return f"{origin}/chat/{workflow_id}"
    root = _API_SUFFIX_PATTERN.sub("", origin)
    return f"{root}/chat/{workflow_id}"


def _enrich_workflow(
    base_url: str,
    workflow: dict[str, Any],
    *,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    enriched = dict(workflow)
    workflow_id = str(enriched.get("id")) if enriched.get("id") else None
    if workflow_id and enriched.get("is_public"):
        if public_base_url:
            enriched["share_url"] = _build_share_url(
                base_url,
                workflow_id,
                public_base_url=public_base_url,
            )
        elif not enriched.get("share_url"):
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
    public_base_url: str | None = None,
) -> dict[str, Any]:
    """Publish a workflow and return the enriched response payload."""
    payload: dict[str, Any] = client.post(
        f"/api/workflows/{workflow_id}/publish",
        json_body={"require_login": require_login, "actor": actor},
    )
    share_url_override = payload.get("share_url")
    public_base_url = public_base_url or client.public_base_url
    workflow = _enrich_workflow(
        client.base_url,
        payload["workflow"],
        public_base_url=public_base_url,
    )
    if share_url_override and not public_base_url:
        workflow["share_url"] = share_url_override
    return {
        "workflow": workflow,
        "message": payload.get("message"),
        "share_url": workflow.get("share_url"),
    }


def unpublish_workflow_data(
    client: ApiClient,
    workflow_id: str,
    *,
    actor: str,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    """Unpublish a workflow and return the enriched payload."""
    workflow: dict[str, Any] = client.post(
        f"/api/workflows/{workflow_id}/publish/revoke",
        json_body={"actor": actor},
    )
    enriched = _enrich_workflow(
        client.base_url,
        workflow,
        public_base_url=public_base_url or client.public_base_url,
    )
    return {"workflow": enriched, "share_url": enriched.get("share_url")}


def enrich_workflow_publish_metadata(
    client: ApiClient,
    workflow: dict[str, Any],
) -> dict[str, Any]:
    """Return ``workflow`` with derived publish metadata (share URL)."""
    return _enrich_workflow(
        client.base_url,
        workflow,
        public_base_url=client.public_base_url,
    )


__all__ = [
    "enrich_workflow_publish_metadata",
    "publish_workflow_data",
    "unpublish_workflow_data",
]
