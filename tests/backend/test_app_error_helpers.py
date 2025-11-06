"""Tests for exception helper functions in ``orcheo_backend.app``."""

from __future__ import annotations
import pytest
from fastapi import HTTPException
from orcheo.triggers.webhook import WebhookValidationError
from orcheo.vault import WorkflowScopeError
from orcheo_backend.app import (
    _raise_conflict,
    _raise_not_found,
    _raise_scope_error,
    _raise_webhook_error,
)


def test_raise_not_found_raises_404() -> None:
    """The _raise_not_found helper raises a 404 HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        _raise_not_found("Test not found", ValueError("test"))
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Test not found"


def test_raise_conflict_raises_409() -> None:
    """The _raise_conflict helper raises a 409 HTTPException."""
    with pytest.raises(HTTPException) as exc_info:
        _raise_conflict("Test conflict", ValueError("test"))
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Test conflict"


def test_raise_webhook_error_raises_with_status_code() -> None:
    """_raise_webhook_error raises HTTPException with webhook error status."""
    webhook_error = WebhookValidationError("Invalid signature", status_code=401)
    with pytest.raises(HTTPException) as exc_info:
        _raise_webhook_error(webhook_error)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid signature"


def test_raise_scope_error_raises_403() -> None:
    """The _raise_scope_error helper raises a 403 HTTPException."""
    scope_error = WorkflowScopeError("Access denied")
    with pytest.raises(HTTPException) as exc_info:
        _raise_scope_error(scope_error)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied"
