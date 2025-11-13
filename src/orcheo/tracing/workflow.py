"""Workflow execution tracing helpers."""

from __future__ import annotations
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any
from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, Tracer
from opentelemetry.trace.span import format_span_id, format_trace_id


_PROMPT_KEYS = {"prompt", "prompts", "messages"}
_RESPONSE_KEYS = {"response", "responses", "output", "outputs", "result", "results"}
_TOKEN_KEYS = {"token_usage", "usage"}
_ARTIFACT_KEYS = {"artifact_ids", "artifacts"}
_MAX_STRING_LENGTH = 2048
_MAX_COLLECTION_ITEMS = 25
_TRUNCATED_SENTINEL = "…"


class WorkflowTrace:
    """Context helper exposing metadata for workflow execution spans."""

    def __init__(self, tracer: Tracer, root_span: Span) -> None:
        """Initialise a workflow trace wrapper for the provided span."""
        self._tracer = tracer
        self._root_span = root_span
        self._trace_id: str | None = None
        self._root_span_id: str | None = None
        self.enabled = False
        context = root_span.get_span_context()
        trace_id = context.trace_id
        if trace_id:
            self._trace_id = format_trace_id(trace_id)
            self._root_span_id = format_span_id(context.span_id)
            self.enabled = True

    @property
    def trace_id(self) -> str | None:
        """Return the trace identifier for the workflow span."""
        return self._trace_id

    @property
    def root_span_id(self) -> str | None:
        """Return the identifier for the root span if available."""
        return self._root_span_id

    @contextmanager
    def start_step_span(
        self,
        name: str,
        *,
        attributes: Mapping[str, Any] | None = None,
    ) -> Iterator[Span | None]:
        """Create a child span for a workflow step if tracing is enabled."""
        if not self.enabled:
            yield None
            return

        with self._tracer.start_as_current_span(name, kind=SpanKind.INTERNAL) as span:
            if attributes:
                for key, value in attributes.items():
                    _set_attribute(span, key, value)
            yield span

    def span_id(self, span: Span | None) -> str | None:
        """Return the formatted span identifier for the provided span."""
        if not self.enabled or span is None:
            return None
        context = span.get_span_context()
        if not context.trace_id:
            return None
        return format_span_id(context.span_id)

    def set_inputs(self, inputs: Mapping[str, Any] | None) -> None:
        """Attach input metadata to the root span."""
        if not self.enabled or not inputs:
            return
        self._root_span.set_attribute("orcheo.workflow.inputs", _stringify(inputs))

    def set_execution_status(self, status: str) -> None:
        """Persist the execution status on the root span."""
        if not self.enabled:
            return
        self._root_span.set_attribute("orcheo.execution.status", status)

    def set_final_state(self, state: Mapping[str, Any] | Any) -> None:
        """Attach the final workflow state to the root span."""
        if not self.enabled:
            return
        self._root_span.set_attribute("orcheo.workflow.final_state", _stringify(state))


@contextmanager
def workflow_execution_span(
    workflow_id: str,
    execution_id: str,
    *,
    inputs: Mapping[str, Any] | None = None,
) -> Iterator[WorkflowTrace]:
    """Context manager that manages the root workflow execution span."""
    tracer = trace.get_tracer("orcheo.workflow")
    with tracer.start_as_current_span(
        "workflow.execution",
        kind=SpanKind.SERVER,
    ) as span:
        span.set_attribute("orcheo.workflow.id", workflow_id)
        span.set_attribute("orcheo.execution.id", execution_id)
        trace_context = WorkflowTrace(tracer, span)
        trace_context.set_inputs(inputs)
        try:
            yield trace_context
            span.set_status(Status(StatusCode.OK))
        except BaseException as exc:  # pragma: no cover - handled by caller tests
            if trace_context.enabled:
                span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise


def derive_step_span_name(index: int, payload: Mapping[str, Any]) -> str:
    """Generate a readable span name for a workflow step payload."""
    if payload and len(payload) == 1:
        key = next(iter(payload))
        if isinstance(key, str) and key:
            return f"workflow.step.{key}"
    return f"workflow.step.{index}"


def build_step_span_attributes(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Collect notable attributes from a workflow step payload."""
    attributes: dict[str, Any] = {}
    if payload:
        attributes["orcheo.step.nodes"] = _truncate_sequence(
            [str(key) for key in payload.keys()]
        )

    prompts, responses, artifacts, token_usage = _collect_step_metadata(payload)
    if prompts:
        attributes["orcheo.step.prompts"] = _truncate_sequence(prompts)
    if responses:
        attributes["orcheo.step.responses"] = _truncate_sequence(responses)
    if artifacts:
        attributes["orcheo.step.artifacts"] = _truncate_sequence(artifacts)
    for key, value in token_usage.items():
        attributes[f"orcheo.step.token_usage.{key}"] = value

    status = payload.get("status") if isinstance(payload, Mapping) else None
    if isinstance(status, str):
        attributes["orcheo.step.status"] = status

    return attributes


def _collect_step_metadata(
    value: Any,
) -> tuple[list[str], list[str], list[str], dict[str, float]]:
    prompts: list[str] = []
    responses: list[str] = []
    artifacts: list[str] = []
    token_usage: dict[str, float] = {}
    _walk_step_metadata(value, prompts, responses, artifacts, token_usage)
    return prompts, responses, artifacts, token_usage


def _walk_step_metadata(
    value: Any,
    prompts: list[str],
    responses: list[str],
    artifacts: list[str],
    token_usage: dict[str, float],
) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in _PROMPT_KEYS:
                prompts.extend(_coerce_strings(item))
            elif lowered in _RESPONSE_KEYS:
                responses.extend(_coerce_strings(item))
            elif lowered in _ARTIFACT_KEYS:
                artifacts.extend(_coerce_strings(item))
            elif lowered in _TOKEN_KEYS:
                _merge_token_usage(token_usage, item)
            else:
                _walk_step_metadata(item, prompts, responses, artifacts, token_usage)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _walk_step_metadata(item, prompts, responses, artifacts, token_usage)


def _merge_token_usage(bucket: dict[str, float], value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            try:
                candidate = str(item)
                bucket[str(key)] = float(candidate)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                continue


def _coerce_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_truncate_string(value)]
    if isinstance(value, Mapping):
        try:
            return [_truncate_string(json.dumps(value, default=str))]
        except TypeError:  # pragma: no cover - defensive
            return [_truncate_string(str(value))]
    if isinstance(value, (list, tuple, set)):
        coerced: list[str] = []
        for item in value:
            coerced.extend(_coerce_strings(item))
        return coerced
    return [_truncate_string(str(value))]


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return _truncate_string(value)
    try:
        return _truncate_string(json.dumps(value, default=str))
    except TypeError:  # pragma: no cover - defensive
        return _truncate_string(str(value))


def _set_attribute(span: Span, key: str, value: Any) -> None:
    if isinstance(value, (str, bool, int, float)):
        span.set_attribute(
            key,
            _truncate_string(value) if isinstance(value, str) else value,
        )
        return
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            span.set_attribute(key, _truncate_sequence(value))
            return
        if all(isinstance(item, (bool, int, float)) for item in value):
            limited = value[:_MAX_COLLECTION_ITEMS]
            span.set_attribute(key, limited)
            if len(value) > _MAX_COLLECTION_ITEMS:
                span.set_attribute(
                    f"{key}.truncated_count", len(value) - _MAX_COLLECTION_ITEMS
                )
            return
    span.set_attribute(key, _stringify(value))


def _truncate_sequence(values: list[str]) -> list[str]:
    if len(values) <= _MAX_COLLECTION_ITEMS and all(
        len(value) <= _MAX_STRING_LENGTH for value in values
    ):
        return values

    truncated: list[str] = []
    for value in values[:_MAX_COLLECTION_ITEMS]:
        truncated.append(_truncate_string(value))
    if len(values) > _MAX_COLLECTION_ITEMS:
        truncated.append(f"...(+{len(values) - _MAX_COLLECTION_ITEMS} more)")
    return truncated


def _truncate_string(value: str) -> str:
    if len(value) <= _MAX_STRING_LENGTH:
        return value
    return value[: _MAX_STRING_LENGTH - 1] + _TRUNCATED_SENTINEL


__all__ = [
    "WorkflowTrace",
    "build_step_span_attributes",
    "derive_step_span_name",
    "workflow_execution_span",
]
