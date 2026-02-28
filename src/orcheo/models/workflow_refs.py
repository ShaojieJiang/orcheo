"""Shared helpers for workflow handles and refs."""

from __future__ import annotations
import re
from uuid import UUID


WORKFLOW_HANDLE_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WORKFLOW_HANDLE_MAX_LENGTH = 64


def normalize_workflow_handle(value: str | None) -> str | None:
    """Normalize an optional workflow handle and validate its format."""
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        msg = "Workflow handle must not be empty."
        raise ValueError(msg)
    if len(normalized) > WORKFLOW_HANDLE_MAX_LENGTH:
        msg = (
            "Workflow handle must be at most "
            f"{WORKFLOW_HANDLE_MAX_LENGTH} characters long."
        )
        raise ValueError(msg)
    if not WORKFLOW_HANDLE_PATTERN.fullmatch(normalized):
        msg = (
            "Workflow handle must contain only lowercase letters, numbers, "
            "and single hyphens."
        )
        raise ValueError(msg)
    return normalized


def workflow_ref_is_uuid(value: str) -> bool:
    """Return whether the provided workflow ref parses as a UUID."""
    try:
        UUID(value)
    except ValueError:
        return False
    return True


__all__ = [
    "WORKFLOW_HANDLE_MAX_LENGTH",
    "WORKFLOW_HANDLE_PATTERN",
    "normalize_workflow_handle",
    "workflow_ref_is_uuid",
]
