"""Backend-specific tracing configuration helpers."""

from __future__ import annotations
import logging
from collections.abc import Mapping
from typing import Any
from orcheo.config.tracing_settings import TracingSettings
from orcheo.tracing import configure_tracer


_logger = logging.getLogger(__name__)


def configure_tracing(settings: Mapping[str, Any] | None) -> None:
    """Configure tracing for the backend application."""
    mapping = dict(settings or {})
    try:
        tracing_settings = TracingSettings.model_validate(mapping)
    except Exception as exc:  # pragma: no cover - defensive
        _logger.error("Invalid tracing configuration: %s", exc)
        return

    configure_tracer(tracing_settings)


__all__ = ["configure_tracing"]
