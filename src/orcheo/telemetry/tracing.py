"""Tracing helpers and configuration utilities for Orcheo services."""

from __future__ import annotations
import logging
from collections.abc import Mapping
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)


_LOGGER = logging.getLogger(__name__)


def configure_tracer_provider(
    *,
    exporter: str,
    service_name: str,
    endpoint: str | None = None,
    headers: Mapping[str, str] | None = None,
    insecure: bool = False,
) -> TracerProvider:
    """Configure and install a tracer provider for the application."""
    exporter_name = exporter.strip().lower()
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if exporter_name == "otlp":
        if endpoint:
            exporter_headers = dict(headers) if headers else None
            if insecure:
                _LOGGER.warning(
                    "OTLP/HTTP exporter does not support insecure transport; "
                    "ignoring ORCHEO_OTEL_EXPORTER_OTLP_INSECURE."
                )
            span_exporter = OTLPSpanExporter(
                endpoint=endpoint,
                headers=exporter_headers,
            )
            provider.add_span_processor(BatchSpanProcessor(span_exporter))
        else:
            _LOGGER.warning(
                "OTLP tracing exporter selected but no endpoint configured; "
                "spans will not be exported."
            )
    elif exporter_name == "console":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    elif exporter_name not in {"none", ""}:
        _LOGGER.warning(
            "Unknown tracing exporter '%s'; spans will not be exported.", exporter
        )

    trace.set_tracer_provider(provider)
    return provider


__all__ = ["configure_tracer_provider"]
