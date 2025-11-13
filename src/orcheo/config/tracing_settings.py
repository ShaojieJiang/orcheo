"""Configuration model describing OpenTelemetry tracing settings."""

from __future__ import annotations
import json
from collections.abc import Mapping
from typing import Any, cast
from pydantic import BaseModel, Field, field_validator
from orcheo.config.defaults import _DEFAULTS


_EXPORTER_KINDS = {"none", "console", "otlp_http"}


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    candidate = str(value).strip().lower()
    if candidate in {"1", "true", "yes", "on"}:
        return True
    if candidate in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_headers(value: object | None) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(key): str(val) for key, val in value.items()}
    text = str(value).strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        headers: dict[str, str] = {}
        for entry in text.split(","):
            if not entry:
                continue
            key, _, val = entry.partition("=")
            if key and val:
                headers[key.strip()] = val.strip()
        return headers
    if isinstance(parsed, Mapping):
        return {str(key): str(val) for key, val in parsed.items()}
    return {}


class TracingSettings(BaseModel):
    """Structured tracing configuration derived from environment variables."""

    enabled: bool = Field(default=bool(_DEFAULTS["TRACING_ENABLED"]))
    service_name: str = Field(default=str(_DEFAULTS["OTEL_SERVICE_NAME"]))
    exporter: str = Field(default=str(_DEFAULTS["OTEL_EXPORTER"]))
    exporter_endpoint: str | None = Field(
        default=None, description="Endpoint for the configured exporter."
    )
    exporter_headers: dict[str, str] = Field(
        default_factory=dict, description="Additional HTTP headers for exporters."
    )
    exporter_timeout: float = Field(
        default=float(cast(float, _DEFAULTS["OTEL_EXPORTER_TIMEOUT"])), ge=0.0
    )

    @field_validator("exporter")
    @classmethod
    def _validate_exporter(cls, value: str) -> str:
        candidate = value.strip().lower()
        if candidate not in _EXPORTER_KINDS:
            msg = "ORCHEO_OTEL_EXPORTER must be one of: none, console, otlp_http."
            raise ValueError(msg)
        return candidate

    @field_validator("service_name", mode="before")
    @classmethod
    def _coerce_service_name(cls, value: object) -> str:
        if value is None:
            return str(_DEFAULTS["OTEL_SERVICE_NAME"])
        return str(value)

    @field_validator("enabled", mode="before")
    @classmethod
    def _coerce_enabled(cls, value: object) -> bool:
        return _coerce_bool(value, bool(_DEFAULTS["TRACING_ENABLED"]))

    @field_validator("exporter_timeout", mode="before")
    @classmethod
    def _coerce_timeout(cls, value: object) -> float:
        if value is None:
            default_timeout = cast(float, _DEFAULTS["OTEL_EXPORTER_TIMEOUT"])
            return float(default_timeout)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            candidate = str(value)
            return float(candidate)
        except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
            raise ValueError("ORCHEO_OTEL_EXPORTER_TIMEOUT must be numeric.") from exc

    @field_validator("exporter_endpoint", mode="before")
    @classmethod
    def _coerce_endpoint(cls, value: object | None) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("exporter_headers", mode="before")
    @classmethod
    def _coerce_headers(cls, value: object | None) -> dict[str, str]:
        return _parse_headers(value)

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any]) -> TracingSettings:
        """Build tracing settings from the raw Dynaconf mapping."""
        return cls(
            enabled=source.get("TRACING_ENABLED", _DEFAULTS["TRACING_ENABLED"]),
            service_name=source.get(
                "OTEL_SERVICE_NAME", _DEFAULTS["OTEL_SERVICE_NAME"]
            ),
            exporter=source.get("OTEL_EXPORTER", _DEFAULTS["OTEL_EXPORTER"]),
            exporter_endpoint=source.get(
                "OTEL_EXPORTER_ENDPOINT", _DEFAULTS["OTEL_EXPORTER_ENDPOINT"]
            ),
            exporter_headers=source.get(
                "OTEL_EXPORTER_HEADERS", _DEFAULTS["OTEL_EXPORTER_HEADERS"]
            ),
            exporter_timeout=source.get(
                "OTEL_EXPORTER_TIMEOUT", _DEFAULTS["OTEL_EXPORTER_TIMEOUT"]
            ),
        )


__all__ = ["TracingSettings"]
