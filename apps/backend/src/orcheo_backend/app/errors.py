"""HTTP error helpers used across routers."""

from __future__ import annotations
from typing import NoReturn
from fastapi import HTTPException, status
from orcheo.triggers.webhook import WebhookValidationError
from orcheo.vault import WorkflowScopeError


def raise_not_found(detail: str, exc: Exception) -> NoReturn:
    """Raise a standardized 404 HTTP error."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    ) from exc


def raise_conflict(detail: str, exc: Exception) -> NoReturn:
    """Raise a standardized 409 HTTP error."""
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    ) from exc


def raise_webhook_error(exc: WebhookValidationError) -> NoReturn:
    """Transform webhook validation errors into HTTP errors."""
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def raise_scope_error(exc: WorkflowScopeError) -> NoReturn:
    """Raise a standardized 403 response for scope violations."""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=str(exc),
    ) from exc


__all__ = [
    "raise_conflict",
    "raise_not_found",
    "raise_scope_error",
    "raise_webhook_error",
]
