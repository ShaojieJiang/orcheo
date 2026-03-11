"""Workflow listener service helpers."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any
from orcheo_sdk.cli.http import ApiClient


def pause_workflow_listener_data(
    client: ApiClient,
    workflow_id: str,
    subscription_id: str,
    *,
    actor: str,
) -> dict[str, Any]:
    """Pause one workflow listener subscription."""
    return _update_workflow_listener_status_data(
        client,
        workflow_id,
        subscription_id,
        action="pause",
        actor=actor,
    )


def resume_workflow_listener_data(
    client: ApiClient,
    workflow_id: str,
    subscription_id: str,
    *,
    actor: str,
) -> dict[str, Any]:
    """Resume one workflow listener subscription."""
    return _update_workflow_listener_status_data(
        client,
        workflow_id,
        subscription_id,
        action="resume",
        actor=actor,
    )


def _update_workflow_listener_status_data(
    client: ApiClient,
    workflow_id: str,
    subscription_id: str,
    *,
    action: str,
    actor: str,
) -> dict[str, Any]:
    payload = client.post(
        f"/api/workflows/{workflow_id}/listeners/{subscription_id}/{action}",
        json_body={"actor": actor},
    )
    if isinstance(payload, Mapping):
        return dict(payload)
    return {}


__all__ = [
    "pause_workflow_listener_data",
    "resume_workflow_listener_data",
]
