"""Unit tests for workflow execution helpers."""

from __future__ import annotations
import contextlib
import importlib
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
import pytest
from orcheo_backend.app import _workflow_execution_module as workflow_execution
from orcheo_backend.app.history import InMemoryRunHistoryStore, RunHistoryError
from orcheo_backend.app.workflow_execution import (
    _persist_failure_history,
    _report_history_error,
    execute_workflow,
)


backend_app_module = importlib.import_module("orcheo_backend.app")


def test_report_history_error_logs_and_updates_tracing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_report_history_error should record tracing metadata and log failures."""

    span = SimpleNamespace()
    exc = RuntimeError("boom")
    calls: list[tuple[Any, Any]] = []
    monkeypatch.setattr(
        workflow_execution,
        "record_workflow_failure",
        lambda span_arg, exc_arg: calls.append((span_arg, exc_arg)),
    )

    class StubLogger:
        def __init__(self) -> None:
            self.messages: list[tuple[str, tuple[Any, ...]]] = []

        def exception(self, message: str, *args: Any) -> None:
            self.messages.append((message, args))

    logger_stub = StubLogger()
    monkeypatch.setattr(workflow_execution, "logger", logger_stub)

    _report_history_error("exec-1", span, exc, context="persist history")

    assert calls == [(span, exc)]
    assert logger_stub.messages == [
        ("Failed to %s for execution %s", ("persist history", "exec-1"))
    ]


@pytest.mark.asyncio
async def test_persist_failure_history_reports_store_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_persist_failure_history tolerates RunHistoryError failures."""

    history_store = AsyncMock()
    failure = RunHistoryError("unavailable")
    history_store.append_step.side_effect = failure
    span = SimpleNamespace()
    reports: list[tuple[str, Any, Exception, str]] = []
    monkeypatch.setattr(
        workflow_execution,
        "_report_history_error",
        lambda execution_id, span_arg, exc, *, context: reports.append(
            (execution_id, span_arg, exc, context)
        ),
    )

    await _persist_failure_history(
        history_store,
        "exec-2",
        {"status": "error"},
        "something failed",
        span,
    )

    assert reports == [
        ("exec-2", span, failure, "record failure state"),
    ]


@pytest.mark.asyncio
async def test_execute_workflow_reports_history_store_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """execute_workflow should surface RunHistoryError exceptions with telemetry."""

    history_store = AsyncMock()
    history_store.start_run = AsyncMock()
    history_store.append_step = AsyncMock()
    history_store.mark_cancelled = AsyncMock()
    history_store.mark_failed = AsyncMock()
    history_store.mark_completed = AsyncMock()
    monkeypatch.setattr(workflow_execution, "get_history_store", lambda: history_store)
    monkeypatch.setattr(workflow_execution, "get_settings", lambda: {"dummy": True})
    monkeypatch.setattr(workflow_execution, "get_vault", lambda: object())
    monkeypatch.setattr(
        workflow_execution, "credential_context_from_workflow", lambda _: {}
    )
    monkeypatch.setattr(
        workflow_execution, "CredentialResolver", lambda *args, **kwargs: object()
    )
    monkeypatch.setattr(
        workflow_execution, "credential_resolution", contextlib.nullcontext
    )

    class DummyCheckpointer:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(
        backend_app_module,
        "create_checkpointer",
        lambda settings: DummyCheckpointer(),
    )

    class DummyGraph:
        def compile(self, *, checkpointer: object) -> object:
            return object()

    monkeypatch.setattr(backend_app_module, "build_graph", lambda config: DummyGraph())
    monkeypatch.setattr(workflow_execution, "get_tracer", lambda name: object())

    class StubSpanContext:
        def __init__(self) -> None:
            self.span = object()
            self.trace_id = "trace-id"
            self.started_at = datetime.now(tz=UTC)

    @contextlib.contextmanager
    def fake_workflow_span(*args: Any, **kwargs: Any):
        yield StubSpanContext()

    monkeypatch.setattr(workflow_execution, "workflow_span", fake_workflow_span)

    run_error = RunHistoryError("history store unavailable")
    stream_mock = AsyncMock(side_effect=run_error)
    monkeypatch.setattr(workflow_execution, "_stream_workflow_updates", stream_mock)
    reports: list[tuple[str, Any, Exception, str]] = []
    monkeypatch.setattr(
        workflow_execution,
        "_report_history_error",
        lambda execution_id, span, exc, *, context: reports.append(
            (execution_id, span, exc, context)
        ),
    )

    class DummyWebSocket:
        def __init__(self) -> None:
            self.messages: list[Any] = []

        async def send_json(self, payload: Any) -> None:
            self.messages.append(payload)

    websocket = DummyWebSocket()

    with pytest.raises(RunHistoryError):
        await execute_workflow(
            workflow_id="00000000-0000-0000-0000-000000000000",
            graph_config={"format": "graph"},
            inputs={"foo": "bar"},
            execution_id="exec-3",
            websocket=websocket,  # type: ignore[arg-type]
        )

    assert len(reports) == 1
    execution_id, span_arg, exc_arg, context = reports[0]
    assert execution_id == "exec-3"
    assert exc_arg is run_error
    assert context == "persist workflow history"


@pytest.mark.asyncio
async def test_stream_workflow_updates_emit_trace_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_stream_workflow_updates should emit trace update messages."""

    history_store = InMemoryRunHistoryStore()
    execution_id = "exec-trace"

    await history_store.start_run(
        workflow_id="wf-1",
        execution_id=execution_id,
        inputs={},
        trace_id="trace-abc",
        trace_started_at=datetime.now(tz=UTC),
    )

    class DummyGraph:
        def __init__(self) -> None:
            self.values: list[dict[str, Any]] = [
                {
                    "llm": {
                        "id": "node-1",
                        "display_name": "LLM",
                        "status": "completed",
                        "token_usage": {"input": 3, "output": 2},
                        "prompts": ["hello"],
                    }
                }
            ]

        async def astream(self, *_: Any, **__: Any):
            for item in self.values:
                yield item

        async def aget_state(self, *_: Any, **__: Any) -> SimpleNamespace:
            return SimpleNamespace(values={})

    class DummyWebSocket:
        def __init__(self) -> None:
            self.messages: list[Any] = []

        async def send_json(self, payload: Any) -> None:
            self.messages.append(payload)

    monkeypatch.setattr(
        workflow_execution,
        "record_workflow_step",
        lambda tracer, step: None,
    )

    websocket = DummyWebSocket()

    graph = DummyGraph()

    await workflow_execution._stream_workflow_updates(
        graph,
        state={},
        config={},
        history_store=history_store,
        execution_id=execution_id,
        websocket=websocket,  # type: ignore[arg-type]
        tracer=SimpleNamespace(),
    )

    assert len(websocket.messages) == 2
    assert websocket.messages[0] == graph.values[0]
    trace_message = websocket.messages[1]
    assert trace_message["type"] == "trace:update"
    assert trace_message["trace_id"] == "trace-abc"
    assert trace_message["spans"][0]["attributes"]["orcheo.token.input"] == 3
