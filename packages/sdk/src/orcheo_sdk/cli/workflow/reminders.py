"""Shared workflow reminder messages for CLI output."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.http import ApiClient
from orcheo_sdk.services import get_workflow_credential_readiness_data


WORKFLOW_VAULT_REMINDER = (
    "Add any required credentials to the vault before running this workflow."
)


def _format_credential_names(names: list[str]) -> str:
    return ", ".join(names)


def _normalize_names(payload: dict[str, Any], field: str) -> list[str]:
    return sorted(
        {
            str(name).strip()
            for name in payload.get(field, [])
            if isinstance(name, str) and str(name).strip()
        }
    )


def describe_workflow_vault_reminder(
    readiness: dict[str, Any] | None,
) -> str | None:
    """Return a human-readable vault reminder string."""
    if not readiness:
        return WORKFLOW_VAULT_REMINDER

    missing = _normalize_names(readiness, "missing_credentials")
    available = _normalize_names(readiness, "available_credentials")
    if missing:
        reminder = (
            "Add these missing vault credentials before running this workflow: "
            f"{_format_credential_names(missing)}."
        )
        if available:  # pragma: no branch
            reminder += (
                " Already available in the vault: "
                f"{_format_credential_names(available)}."
            )
        return reminder
    return None


def fetch_workflow_vault_readiness(
    client: ApiClient,
    workflow_id: str | None,
) -> dict[str, Any] | None:
    """Return workflow readiness data without interrupting the main command."""
    if not workflow_id:
        return None

    try:
        return get_workflow_credential_readiness_data(client, workflow_id)
    except Exception:  # noqa: BLE001 - reminder lookup must stay best-effort
        return None


def attach_workflow_vault_reminder(
    payload: dict[str, Any],
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a payload copy with the vault reminder attached."""
    updated = dict(payload)
    reminder = describe_workflow_vault_reminder(readiness)
    if reminder is not None:
        updated["credential_vault_reminder"] = reminder
    if readiness is not None:
        updated["credential_readiness"] = readiness
    return updated


__all__ = [
    "WORKFLOW_VAULT_REMINDER",
    "attach_workflow_vault_reminder",
    "describe_workflow_vault_reminder",
    "fetch_workflow_vault_readiness",
]
