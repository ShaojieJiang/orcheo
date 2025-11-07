"""ChatKit runtime helpers."""

from __future__ import annotations
import pytest
from orcheo_backend.app.chatkit_runtime import sensitive_logging_enabled


def test_sensitive_logging_enabled_accepts_dev_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Development-like env vars enable sensitive logging."""
    monkeypatch.setenv("ORCHEO_ENV", "DEV")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("NODE_ENV", raising=False)
    monkeypatch.delenv("LOG_SENSITIVE_DEBUG", raising=False)

    assert sensitive_logging_enabled() is True
