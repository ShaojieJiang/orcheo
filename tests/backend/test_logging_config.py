"""Tests for Orcheo backend logging helpers."""

from __future__ import annotations
import importlib
import logging
import pytest


logging_config = importlib.import_module("orcheo_backend.app.logging_config")


def _logger_names() -> tuple[str, ...]:
    return (
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "orcheo",
        "orcheo_backend",
    )


def test_configure_logging_applies_requested_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reloading the module applies LOG_LEVEL to the known logger names."""
    monkeypatch.setenv("LOG_LEVEL", "debug")
    reloaded = importlib.reload(logging_config)

    for name in _logger_names():
        assert logging.getLogger(name).level == logging.DEBUG

    assert reloaded.get_logger().name == "orcheo_backend.app"
    assert reloaded.get_logger("custom.logger").name == "custom.logger"
