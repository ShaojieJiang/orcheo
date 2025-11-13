"""Telemetry configuration models and helpers."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Literal, cast
from pydantic import BaseModel, Field
from orcheo.config.defaults import _DEFAULTS


TelemetryExporter = Literal["otlp", "console", "inmemory"]
TelemetrySampler = Literal["always_on", "always_off", "ratio"]

_ALLOWED_EXPORTERS = {"otlp", "console", "inmemory"}
_ALLOWED_SAMPLERS = {"always_on", "always_off", "ratio"}


class TelemetrySettings(BaseModel):
    """Application telemetry configuration backed by environment variables."""

    enabled: bool = Field(default=bool(_DEFAULTS["TELEMETRY_ENABLED"]))
    service_name: str = Field(default=str(_DEFAULTS["TELEMETRY_SERVICE_NAME"]))
    exporter: TelemetryExporter = Field(
        default=cast(TelemetryExporter, _DEFAULTS["TELEMETRY_EXPORTER"])
    )
    exporter_otlp_endpoint: str | None = None
    exporter_otlp_headers: dict[str, str] = Field(default_factory=dict)
    exporter_otlp_insecure: bool = Field(
        default=bool(_DEFAULTS["TELEMETRY_EXPORTER_OTLP_INSECURE"])
    )
    exporter_otlp_timeout: float | None = Field(
        default=cast(float, _DEFAULTS["TELEMETRY_EXPORTER_OTLP_TIMEOUT"])
    )
    sampler: TelemetrySampler = Field(
        default=cast(TelemetrySampler, _DEFAULTS["TELEMETRY_SAMPLER"])
    )
    sampler_ratio: float = Field(
        default=cast(float, _DEFAULTS["TELEMETRY_SAMPLER_RATIO"])
    )

    @classmethod
    def from_mapping(cls, source: Mapping[str, Any] | None) -> TelemetrySettings:
        """Create settings from a mapping or Dynaconf instance."""
        raw = _coerce_mapping(source)
        # Normalized configuration stores snake_case keys matching the model.
        if any(key in raw for key in ("enabled", "service_name", "exporter")):
            headers = raw.get("exporter_otlp_headers") or {}
            if isinstance(headers, str):
                headers = _parse_headers(headers)
            exporter_value = cast(
                TelemetryExporter,
                _coerce_choice(
                    raw.get("exporter"),
                    allowed=_ALLOWED_EXPORTERS,
                    default=str(cls.model_fields["exporter"].default).lower(),
                ),
            )
            sampler_value = cast(
                TelemetrySampler,
                _coerce_choice(
                    raw.get("sampler"),
                    allowed=_ALLOWED_SAMPLERS,
                    default=str(cls.model_fields["sampler"].default).lower(),
                ),
            )
            return cls(
                enabled=_to_bool(
                    raw.get("enabled"), default=cls.model_fields["enabled"].default
                ),
                service_name=str(
                    raw.get("service_name", cls.model_fields["service_name"].default)
                ),
                exporter=exporter_value,
                exporter_otlp_endpoint=_to_optional_str(
                    raw.get("exporter_otlp_endpoint")
                ),
                exporter_otlp_headers=_ensure_str_dict(headers),
                exporter_otlp_insecure=_to_bool(
                    raw.get("exporter_otlp_insecure"),
                    default=cls.model_fields["exporter_otlp_insecure"].default,
                ),
                exporter_otlp_timeout=_to_optional_float(
                    raw.get("exporter_otlp_timeout"),
                    default=cast(
                        float | None,
                        cls.model_fields["exporter_otlp_timeout"].default,
                    ),
                ),
                sampler=sampler_value,
                sampler_ratio=_to_ratio(
                    raw.get("sampler_ratio"),
                    default=cast(float, _DEFAULTS["TELEMETRY_SAMPLER_RATIO"]),
                ),
            )

        exporter = cast(
            TelemetryExporter,
            _coerce_choice(
                raw.get("TELEMETRY_EXPORTER", _DEFAULTS["TELEMETRY_EXPORTER"]),
                allowed=_ALLOWED_EXPORTERS,
                default=str(_DEFAULTS["TELEMETRY_EXPORTER"]).lower(),
            ),
        )
        headers_value = raw.get("TELEMETRY_EXPORTER_OTLP_HEADERS")
        if headers_value is None:
            headers_value = raw.get("OTEL_EXPORTER_OTLP_HEADERS")

        sampler = cast(
            TelemetrySampler,
            _coerce_choice(
                raw.get("TELEMETRY_SAMPLER", _DEFAULTS["TELEMETRY_SAMPLER"]),
                allowed=_ALLOWED_SAMPLERS,
                default=str(_DEFAULTS["TELEMETRY_SAMPLER"]).lower(),
            ),
        )
        sampler_ratio = _to_ratio(
            raw.get("TELEMETRY_SAMPLER_RATIO", raw.get("OTEL_TRACES_SAMPLER_ARG")),
            default=cast(float, _DEFAULTS["TELEMETRY_SAMPLER_RATIO"]),
        )

        timeout_value = raw.get("TELEMETRY_EXPORTER_OTLP_TIMEOUT")
        if timeout_value is None:
            timeout_value = raw.get("OTEL_EXPORTER_OTLP_TIMEOUT")

        endpoint = raw.get("TELEMETRY_EXPORTER_OTLP_ENDPOINT")
        if endpoint is None:
            endpoint = raw.get("OTEL_EXPORTER_OTLP_ENDPOINT")

        return cls(
            enabled=_to_bool(
                raw.get("TELEMETRY_ENABLED"),
                default=_DEFAULTS["TELEMETRY_ENABLED"],
            ),
            service_name=str(
                raw.get("TELEMETRY_SERVICE_NAME", _DEFAULTS["TELEMETRY_SERVICE_NAME"])
            ),
            exporter=exporter,
            exporter_otlp_endpoint=_to_optional_str(endpoint),
            exporter_otlp_headers=_ensure_str_dict(headers_value),
            exporter_otlp_insecure=_to_bool(
                raw.get("TELEMETRY_EXPORTER_OTLP_INSECURE"),
                default=_DEFAULTS["TELEMETRY_EXPORTER_OTLP_INSECURE"],
            ),
            exporter_otlp_timeout=_to_optional_float(
                timeout_value,
                default=cast(float, _DEFAULTS["TELEMETRY_EXPORTER_OTLP_TIMEOUT"]),
            ),
            sampler=sampler,
            sampler_ratio=sampler_ratio,
        )


def _coerce_mapping(source: Mapping[str, Any] | None) -> dict[str, Any]:
    if source is None:
        return {}
    if hasattr(source, "as_dict"):
        return dict(source.as_dict())  # type: ignore[call-arg]
    if isinstance(source, Mapping):
        return dict(source)
    return {}


def _to_bool(value: Any, *, default: Any) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def _to_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_optional_float(value: Any, *, default: float | None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_ratio(value: Any, *, default: float) -> float:
    candidate = _to_optional_float(value, default=default)
    if candidate is None:
        return default
    return max(0.0, min(1.0, candidate))


def _ensure_str_dict(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return {str(key): str(val) for key, val in value.items()}
    if isinstance(value, str):
        return _parse_headers(value)
    return {}


def _parse_headers(value: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    if not value:
        return headers
    for pair in value.replace(";", ",").split(","):
        if "=" not in pair:
            continue
        key, header_value = pair.split("=", 1)
        key = key.strip()
        header_value = header_value.strip()
        if key and header_value:
            headers[key] = header_value
    return headers


def _coerce_choice(
    value: Any,
    *,
    allowed: set[str],
    default: str,
) -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in allowed:
            return candidate
    return default


__all__ = ["TelemetryExporter", "TelemetrySampler", "TelemetrySettings"]
