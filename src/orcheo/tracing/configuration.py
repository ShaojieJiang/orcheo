"""Helpers for configuring OpenTelemetry tracing providers."""

from __future__ import annotations
import logging
from threading import Lock
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from requests import RequestException
from orcheo.config.tracing_settings import TracingSettings


_logger = logging.getLogger(__name__)
_CONFIG_LOCK = Lock()
_CONFIGURED = False


def configure_tracer(settings: TracingSettings) -> None:
    """Configure the global tracer provider based on the supplied settings."""
    if not settings.enabled:
        _logger.debug("Tracing disabled; skipping tracer configuration.")
        return

    exporter = _build_exporter(settings)
    if exporter is None:
        _logger.warning(
            "Tracing enabled but no exporter configured; spans will be dropped."
        )
        return

    processor = BatchSpanProcessor(exporter)

    global _CONFIGURED  # noqa: PLW0603 - module level state guard
    with _CONFIG_LOCK:
        if _CONFIGURED:
            return

        resource = Resource.create({"service.name": settings.service_name})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        _CONFIGURED = True


def _build_exporter(settings: TracingSettings) -> SpanExporter | None:
    """Instantiate the exporter defined in the tracing settings."""
    exporter_kind = settings.exporter
    if exporter_kind == "none":
        return None
    if exporter_kind == "console":
        return ConsoleSpanExporter()
    if exporter_kind == "otlp_http":
        try:
            return OTLPSpanExporter(
                endpoint=settings.exporter_endpoint,
                headers=settings.exporter_headers or None,
                timeout=settings.exporter_timeout,
            )
        except (
            RequestException,
            TypeError,
            ValueError,
        ) as exc:  # pragma: no cover - defensive
            _logger.exception("Failed to configure OTLP exporter: %s", exc)
            return None

    _logger.warning("Unsupported OpenTelemetry exporter configured: %s", exporter_kind)
    return None


__all__ = ["configure_tracer"]
