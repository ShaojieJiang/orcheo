"""Tracing configuration and helper utilities for workflow execution."""

from __future__ import annotations
import json
from collections.abc import Mapping, Sequence
from typing import Any
from dynaconf import Dynaconf
from opentelemetry import trace
from opentelemetry.trace import Span
from orcheo.config import get_settings
from orcheo.telemetry import configure_tracer_provider


_TRACER = trace.get_tracer("orcheo_backend.workflow")
_MAX_ATTR_LENGTH = 4096
_PROMPT_KEYS = ("prompt", "instruction", "input")
_RESPONSE_KEYS = ("response", "output", "result", "message")
_ARTIFACT_KEYS = ("artifacts", "files", "attachments")


def configure_tracing(settings: Dynaconf | None = None) -> None:
    """Configure the tracer provider using application settings."""
    config = settings or get_settings()
    exporter = str(config.get("TRACING_EXPORTER", "none"))
    service_name = str(config.get("TRACING_SERVICE_NAME", "orcheo-backend"))
    endpoint = config.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    headers = config.get("OTEL_EXPORTER_OTLP_HEADERS") or {}
    insecure = bool(config.get("OTEL_EXPORTER_OTLP_INSECURE"))

    configure_tracer_provider(
        exporter=exporter,
        service_name=service_name,
        endpoint=endpoint,
        headers=headers,
        insecure=insecure,
    )


def get_workflow_tracer() -> trace.Tracer:
    """Return the tracer instance used for workflow execution spans."""
    return _TRACER


def workflow_span_attributes(*, workflow_id: str, execution_id: str) -> dict[str, str]:
    """Return base attributes for the workflow execution span."""
    return {
        "workflow.id": workflow_id,
        "workflow.execution_id": execution_id,
    }


def add_workflow_inputs_event(span: Span, inputs: Mapping[str, Any]) -> None:
    """Record the initial workflow inputs on the provided span."""
    span.add_event("workflow.inputs", attributes={"inputs": _stringify(inputs)})


def format_trace_identifiers(span: Span) -> tuple[str, str]:
    """Return hexadecimal trace and span identifiers for persistence."""
    context = span.get_span_context()
    trace_id = f"{context.trace_id:032x}"
    span_id = f"{context.span_id:016x}"
    return trace_id, span_id


def build_step_span_attributes(
    *, step_index: int, node_name: str, payload: Mapping[str, Any] | Any
) -> dict[str, Any]:
    """Construct span attributes for a workflow node execution."""
    attributes: dict[str, Any] = {
        "workflow.step.index": step_index,
        "workflow.step.node": node_name,
    }
    attributes.update(_extract_step_metadata(payload))
    return attributes


def add_step_event(
    span: Span, *, step_index: int, node_name: str, payload: Mapping[str, Any] | Any
) -> None:
    """Attach a structured event describing a workflow step to the span."""
    span.add_event(
        "workflow.step",
        attributes={
            "index": step_index,
            "node": node_name,
            "payload": _stringify(payload),
        },
    )


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str, ensure_ascii=False)
        except TypeError:  # pragma: no cover - defensive
            text = str(value)
    if len(text) <= _MAX_ATTR_LENGTH:
        return text
    return text[:_MAX_ATTR_LENGTH]


def _extract_step_metadata(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    prompt = _find_text(payload, _PROMPT_KEYS)
    if prompt:
        metadata["workflow.step.prompt"] = prompt
    response = _find_text(payload, _RESPONSE_KEYS)
    if response:
        metadata["workflow.step.response"] = response

    token_counts = _collect_token_counts(payload)
    metadata.update(token_counts)

    artifacts = _collect_artifact_ids(payload)
    if artifacts:
        unique_artifacts = list(dict.fromkeys(artifacts))
        metadata["workflow.step.artifact_ids"] = ",".join(unique_artifacts)
        metadata["workflow.step.artifact_count"] = len(unique_artifacts)

    return metadata


def _find_text(value: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, Mapping) or (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    ):
        for key, candidate in _iter_named_values(value):
            lowered = key.lower()
            if any(marker in lowered for marker in keys):
                text = _coerce_text(candidate)
                if text:
                    return text
    return None


def _coerce_text(value: Any) -> str | None:
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, Mapping):
        for candidate_key in ("text", "content", "value"):
            candidate_value = value.get(candidate_key)
            if isinstance(candidate_value, str):
                return _truncate(candidate_value)
            coerced = _coerce_text(candidate_value)
            if coerced:
                return coerced
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts = [
            segment for segment in (_coerce_text(item) for item in value) if segment
        ]
        if parts:
            return _truncate("\n".join(parts))
    elif value is not None:
        text = str(value)
        if text:
            return _truncate(text)
    return None


def _collect_token_counts(value: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, candidate in _iter_named_values(value):
        lowered = key.lower()
        token_value = _coerce_int(candidate)
        if token_value is None:
            continue
        if "prompt_token" in lowered:
            counts.setdefault("workflow.step.prompt_tokens", token_value)
        elif "completion_token" in lowered:
            counts.setdefault("workflow.step.completion_tokens", token_value)
        elif "total_token" in lowered:
            counts.setdefault("workflow.step.total_tokens", token_value)
    return counts


def _collect_artifact_ids(value: Any) -> list[str]:
    artifacts: list[str] = []

    def _walk(candidate: Any) -> None:
        if isinstance(candidate, Mapping):
            for key, item in candidate.items():
                lowered = key.lower()
                if any(marker in lowered for marker in _ARTIFACT_KEYS):
                    artifacts.extend(_extract_artifact_ids(item))
                else:
                    _walk(item)
        elif isinstance(candidate, Sequence) and not isinstance(
            candidate, (str, bytes, bytearray)
        ):
            for item in candidate:
                _walk(item)

    _walk(value)
    return [artifact for artifact in artifacts if artifact]


def _iter_named_values(value: Any) -> list[tuple[str, Any]]:
    stack: list[Any] = [value]
    pairs: list[tuple[str, Any]] = []
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            for key, item in current.items():
                pairs.append((key, item))
                stack.append(item)
        elif isinstance(current, Sequence) and not isinstance(
            current, (str, bytes, bytearray)
        ):
            stack.extend(current)
    return pairs


def _extract_artifact_ids(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        ids: list[str] = []
        if isinstance(value.get("id"), str):
            ids.append(str(value["id"]))
        for item in value.values():
            if item is value.get("id"):
                continue
            ids.extend(_extract_artifact_ids(item))
        return ids
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        collected: list[str] = []
        for item in value:
            collected.extend(_extract_artifact_ids(item))
        return collected
    return []


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, bool):  # pragma: no cover - defensive
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _truncate(text: str) -> str:
    if len(text) <= _MAX_ATTR_LENGTH:
        return text
    return text[:_MAX_ATTR_LENGTH]


__all__ = [
    "add_step_event",
    "add_workflow_inputs_event",
    "build_step_span_attributes",
    "configure_tracing",
    "format_trace_identifiers",
    "get_workflow_tracer",
    "workflow_span_attributes",
]
