"""Workflow runnable-config persistence helpers."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.http import ApiClient


def _resolve_version_number(
    client: ApiClient,
    workflow_id: str,
    *,
    version: int | None,
) -> int:
    """Resolve a concrete version number for config-only updates."""
    if version is not None:
        return version
    versions = client.get(f"/api/workflows/{workflow_id}/versions")
    if not versions:
        msg = (
            f"Workflow '{workflow_id}' has no versions. "
            "Ingest a Python LangGraph script first."
        )
        raise CLIError(msg)
    latest = max(versions, key=lambda entry: entry.get("version", 0))
    resolved = latest.get("version")
    if not isinstance(resolved, int):
        msg = f"Workflow '{workflow_id}' returned an invalid version payload."
        raise CLIError(msg)
    return resolved


def save_workflow_runnable_config_data(
    client: ApiClient,
    workflow_id: str,
    *,
    runnable_config: dict[str, Any] | None,
    actor: str,
    version: int | None = None,
) -> dict[str, Any]:
    """Persist runnable config on an existing workflow version."""
    version_number = _resolve_version_number(client, workflow_id, version=version)
    payload = {
        "runnable_config": runnable_config,
        "actor": actor,
    }
    try:
        updated_version = client.put(
            f"/api/workflows/{workflow_id}/versions/{version_number}/runnable-config",
            json_body=payload,
        )
    except Exception as exc:
        raise CLIError(
            f"Failed to save runnable config for workflow '{workflow_id}' "
            f"version {version_number}: {exc}"
        ) from exc
    return {
        "workflow_id": workflow_id,
        "version": version_number,
        "runnable_config": updated_version.get("runnable_config"),
        "updated_version": updated_version,
    }


__all__ = ["save_workflow_runnable_config_data"]
