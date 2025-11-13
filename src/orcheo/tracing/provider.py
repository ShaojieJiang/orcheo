"""Helpers for configuring OpenTelemetry tracing."""

from __future__ import annotations
import logging
from dataclasses import dataclass
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.sdk.trace.sampling import (
    Decision,
    Sampler,
    StaticSampler,
    TraceIdRatioBased,
)
from opentelemetry.util._once import Once
from orcheo.config import TelemetrySettings, get_settings


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _TracingState:
    provider: TracerProvider | None = None
    exporter: SpanExporter | None = None
    enabled: bool = False


_STATE = _TracingState()


def configure_global_tracing(
    settings: TelemetrySettings | None = None,
    *,
    exporter: SpanExporter | None = None,
    force: bool = False,
) -> TracerProvider | None:
    """Configure the global tracer provider using the supplied settings."""
    if _STATE.provider is not None and not force:
        return _STATE.provider

    telemetry_settings = settings or _load_settings()
    provider, configured_exporter = _configure_provider(
        telemetry_settings, exporter=exporter
    )
    _STATE.provider = provider
    _STATE.exporter = configured_exporter
    _STATE.enabled = telemetry_settings.enabled and provider is not None
    return provider


def reset_tracing() -> None:
    """Reset tracing configuration to a clean state (primarily for testing)."""
    _STATE.provider = None
    _STATE.exporter = None
    _STATE.enabled = False
    if hasattr(trace, "_TRACER_PROVIDER_SET_ONCE"):
        trace._TRACER_PROVIDER_SET_ONCE = Once()  # type: ignore[attr-defined]
    if hasattr(trace, "_TRACER_PROVIDER"):
        trace._TRACER_PROVIDER = None  # type: ignore[attr-defined]


def is_tracing_enabled() -> bool:
    """Return ``True`` when telemetry is enabled and configured."""
    return _STATE.enabled


def get_configured_exporter() -> SpanExporter | None:
    """Expose the exporter configured during setup (useful for tests)."""
    return _STATE.exporter


def _load_settings() -> TelemetrySettings:
    raw_settings = get_settings()
    candidate = raw_settings.get("TELEMETRY")
    if isinstance(candidate, dict):
        return TelemetrySettings.from_mapping(candidate)
    return TelemetrySettings.from_mapping(raw_settings)


def _configure_provider(
    settings: TelemetrySettings,
    *,
    exporter: SpanExporter | None = None,
) -> tuple[TracerProvider | None, SpanExporter | None]:
    if not settings.enabled:
        logger.info("Telemetry disabled via configuration; skipping tracer setup.")
        return None, None

    sampler = _build_sampler(settings)
    resource = Resource.create({"service.name": settings.service_name})
    provider = TracerProvider(resource=resource, sampler=sampler)
    span_exporter = exporter or _build_exporter(settings)
    if span_exporter is not None:
        processor = (
            BatchSpanProcessor(span_exporter)
            if settings.exporter == "otlp"
            else SimpleSpanProcessor(span_exporter)
        )
        provider.add_span_processor(processor)
    else:
        logger.warning(
            "No span exporter configured; spans will not be shipped to a collector."
        )

    if hasattr(trace, "_set_tracer_provider"):
        trace._set_tracer_provider(provider, False)  # type: ignore[attr-defined]
    else:  # pragma: no cover - fallback for older SDKs
        trace.set_tracer_provider(provider)
    return provider, span_exporter


def _build_exporter(settings: TelemetrySettings) -> SpanExporter | None:
    exporter = settings.exporter
    if exporter == "otlp":
        if not settings.exporter_otlp_endpoint:
            logger.warning(
                "Telemetry exporter 'otlp' selected but no endpoint configured."
            )
            return None
        headers = settings.exporter_otlp_headers or None
        if settings.exporter_otlp_insecure and (
            settings.exporter_otlp_endpoint.startswith("https://")
        ):
            logger.warning(
                "exporter_otlp_insecure is set but the HTTP OTLP exporter does not "
                "support disabling TLS verification; consider using an http:// "
                "endpoint or providing custom certificates."
            )
        return OTLPSpanExporter(
            endpoint=settings.exporter_otlp_endpoint,
            headers=headers,
            timeout=settings.exporter_otlp_timeout,
        )
    if exporter == "console":
        return ConsoleSpanExporter()
    if exporter == "inmemory":
        return InMemorySpanExporter()
    logger.warning(
        "Unknown telemetry exporter '%s'; falling back to console.", exporter
    )
    return ConsoleSpanExporter()


def _build_sampler(settings: TelemetrySettings) -> Sampler:
    sampler = settings.sampler
    if sampler == "always_off":
        return StaticSampler(Decision.DROP)
    if sampler == "ratio":
        return TraceIdRatioBased(settings.sampler_ratio)
    return StaticSampler(Decision.RECORD_AND_SAMPLE)


__all__ = [
    "configure_global_tracing",
    "get_configured_exporter",
    "is_tracing_enabled",
    "reset_tracing",
]
