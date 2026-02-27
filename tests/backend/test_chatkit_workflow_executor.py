"""Tests for the ChatKit workflow executor helper."""

from __future__ import annotations
from collections.abc import Mapping
from contextlib import asynccontextmanager, nullcontext
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from orcheo_backend.app.chatkit import workflow_executor as workflow_executor_module
from orcheo_backend.app.chatkit.workflow_executor import (
    WorkflowExecutor,
    _append_chatkit_history_step,
    _mark_chatkit_history_completed,
    _mark_chatkit_history_failed,
    _start_chatkit_history,
)
from orcheo_backend.app.history import RunHistoryError


class CustomMapping(Mapping[str, object]):
    """Mapping wrapper used to simulate non-dict state views."""

    def __init__(self, data: dict[str, object]) -> None:
        self._data = data

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, key: str) -> object:
        return self._data[key]


class CustomState(BaseModel):
    reply: str
    messages: list[HumanMessage] = Field(default_factory=list)

    def model_dump(self, *args: object, **kwargs: object) -> CustomMapping:
        return CustomMapping({"reply": self.reply})


def test_extract_messages_filters_only_base_messages() -> None:
    message = HumanMessage(content="hello")
    payload = {"messages": [message, "ignore"]}
    assert WorkflowExecutor._extract_messages(payload) == [message]


def test_extract_messages_attribute_branch_non_mapping() -> None:
    class Container:
        def __init__(self, messages: list[HumanMessage]) -> None:
            self.messages = messages

    message = HumanMessage(content="attr")
    container = Container([message])
    assert WorkflowExecutor._extract_messages(container) == [message]


def test_extract_messages_uses_attribute_access() -> None:
    class Container:
        def __init__(self, messages: list[HumanMessage]):
            self.messages = messages

    message = HumanMessage(content="world")
    container = Container([message])
    assert WorkflowExecutor._extract_messages(container) == [message]


@asynccontextmanager
async def fake_checkpointer(_settings: object | None):
    yield object()


class DummyCompiledGraph:
    def __init__(self, final_state: CustomState) -> None:
        self._final_state = final_state

    async def ainvoke(self, *args: object, **kwargs: object) -> CustomState:
        return self._final_state


class DummyGraph:
    def __init__(self, final_state: CustomState) -> None:
        self._final_state = final_state
        self.last_store: object | None = None

    def compile(
        self,
        *,
        checkpointer: object,
        store: object | None = None,
    ) -> DummyCompiledGraph:
        self.last_store = store
        del checkpointer, store
        return DummyCompiledGraph(self._final_state)


class DummyStateSnapshot:
    def __init__(self, values: CustomState) -> None:
        self.values = values


class DummyStreamingCompiledGraph:
    def __init__(
        self, steps: list[dict[str, object]], final_state: CustomState
    ) -> None:
        self._steps = steps
        self._final_state = final_state

    async def astream(self, *_args: object, **_kwargs: object):
        for step in self._steps:
            yield step

    async def aget_state(self, *_args: object, **_kwargs: object) -> DummyStateSnapshot:
        return DummyStateSnapshot(self._final_state)


class DummyStreamingGraph:
    def __init__(
        self, steps: list[dict[str, object]], final_state: CustomState
    ) -> None:
        self._steps = steps
        self._final_state = final_state
        self.last_store: object | None = None

    def compile(
        self,
        *,
        checkpointer: object,
        store: object | None = None,
    ) -> DummyStreamingCompiledGraph:
        self.last_store = store
        del checkpointer, store
        return DummyStreamingCompiledGraph(self._steps, self._final_state)


@pytest.mark.asyncio
async def test_run_inserts_raw_messages_and_records_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = Mock(
        id="version",
        graph={"format": "standard"},
        runnable_config=None,
    )
    repository = AsyncMock()
    repository.get_latest_version.return_value = version
    run_record = Mock(id="run-id")
    repository.create_run.return_value = run_record
    repository.mark_run_started = AsyncMock()
    repository.mark_run_succeeded = AsyncMock()
    history_store = AsyncMock()

    final_state = CustomState(
        reply="final reply", messages=[HumanMessage(content="payload")]
    )
    graph = DummyGraph(final_state)

    monkeypatch.setattr(workflow_executor_module, "get_settings", lambda: None)
    monkeypatch.setattr(
        workflow_executor_module,
        "get_history_store",
        lambda: history_store,
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "create_checkpointer",
        fake_checkpointer,
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "create_graph_store",
        fake_checkpointer,
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "build_graph",
        lambda config: graph,
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "credential_resolution",
        lambda _: nullcontext(),  # type: ignore[assignment]
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "CredentialResolver",
        lambda vault, context: Mock(),
    )
    monkeypatch.setattr(
        workflow_executor_module.WorkflowExecutor,
        "_extract_messages",
        staticmethod(lambda _: [HumanMessage(content="payload")]),
    )

    executor = WorkflowExecutor(repository=repository, vault_provider=lambda: None)
    reply, state_view, run = await executor.run(uuid4(), {"input": "value"})

    assert reply == "final reply"
    assert "_messages" in state_view
    assert state_view["_messages"][0].content == "payload"
    assert run is run_record
    assert graph.last_store is not None
    repository.mark_run_succeeded.assert_awaited_once_with(
        run_record.id, actor="chatkit", output={"reply": "final reply"}
    )
    history_store.start_run.assert_awaited_once()
    history_store.mark_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_streams_progress_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = Mock(
        id="version",
        graph={"format": "standard"},
        runnable_config=None,
    )
    repository = AsyncMock()
    repository.get_latest_version.return_value = version
    repository.create_run.return_value = Mock(id="run-id")
    repository.mark_run_started = AsyncMock()
    repository.mark_run_succeeded = AsyncMock()
    history_store = AsyncMock()

    steps = [{"node_a": {"value": 1}}, {"node_b": {"value": 2}}]
    final_state = CustomState(
        reply="final reply", messages=[HumanMessage(content="payload")]
    )
    graph = DummyStreamingGraph(steps, final_state)

    monkeypatch.setattr(workflow_executor_module, "get_settings", lambda: None)
    monkeypatch.setattr(
        workflow_executor_module,
        "get_history_store",
        lambda: history_store,
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "create_checkpointer",
        fake_checkpointer,
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "create_graph_store",
        fake_checkpointer,
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "build_graph",
        lambda config: graph,
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "credential_resolution",
        lambda _: nullcontext(),  # type: ignore[assignment]
    )
    monkeypatch.setattr(
        workflow_executor_module,
        "CredentialResolver",
        lambda vault, context: Mock(),
    )

    captured_steps: list[dict[str, object]] = []

    async def progress_callback(step: Mapping[str, object]) -> None:
        captured_steps.append(dict(step))

    executor = WorkflowExecutor(repository=repository, vault_provider=lambda: None)
    reply, state_view, run = await executor.run(
        uuid4(), {"input": "value"}, progress_callback=progress_callback
    )

    assert captured_steps == steps
    assert reply == "final reply"
    assert "_messages" in state_view
    assert run is not None
    assert graph.last_store is not None
    repository.mark_run_succeeded.assert_awaited_once()
    history_store.start_run.assert_awaited_once()
    assert history_store.append_step.await_count >= len(steps)
    history_store.mark_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_chatkit_history_logs_run_history_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history_store = AsyncMock()
    history_store.start_run.side_effect = RunHistoryError("boom")
    merged_config = Mock()
    merged_config.to_json_config.return_value = {"configurable": {"thread_id": "x"}}
    merged_config.tags = []
    merged_config.callbacks = []
    merged_config.metadata = {}
    merged_config.run_name = None
    logger = Mock()
    monkeypatch.setattr(workflow_executor_module, "logger", logger)

    await _start_chatkit_history(
        history_store=history_store,
        workflow_id=uuid4(),
        execution_id="exec-1",
        inputs={"a": 1},
        merged_config=merged_config,
    )

    logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_append_history_step_logs_run_history_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history_store = AsyncMock()
    history_store.append_step.side_effect = RunHistoryError("boom")
    logger = Mock()
    monkeypatch.setattr(workflow_executor_module, "logger", logger)

    await _append_chatkit_history_step(history_store, "exec-1", {"node": "x"})

    logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_mark_history_completed_logs_run_history_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history_store = AsyncMock()
    history_store.append_step.side_effect = RunHistoryError("boom")
    logger = Mock()
    monkeypatch.setattr(workflow_executor_module, "logger", logger)

    await _mark_chatkit_history_completed(history_store, "exec-1")

    logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_mark_history_failed_logs_run_history_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    history_store = AsyncMock()
    history_store.append_step.side_effect = RunHistoryError("boom")
    logger = Mock()
    monkeypatch.setattr(workflow_executor_module, "logger", logger)

    await _mark_chatkit_history_failed(history_store, "exec-1", "failed")

    logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_build_step_callback_without_progress_callback() -> None:
    history_store = AsyncMock()
    executor = WorkflowExecutor(repository=AsyncMock(), vault_provider=lambda: None)

    step_callback = executor._build_step_callback(
        history_store=history_store,
        execution_id="exec-1",
        progress_callback=None,
    )
    await step_callback({"node": {"ok": True}})

    history_store.append_step.assert_awaited_once_with("exec-1", {"node": {"ok": True}})


@pytest.mark.asyncio
async def test_record_run_failure_returns_early_when_run_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = AsyncMock()
    executor = WorkflowExecutor(repository=repository, vault_provider=lambda: None)
    history_store = AsyncMock()
    mark_failed = AsyncMock()
    monkeypatch.setattr(
        workflow_executor_module, "_mark_chatkit_history_failed", mark_failed
    )

    await executor._record_run_failure(
        run=None,
        actor="chatkit",
        history_store=history_store,
        execution_id="exec-1",
        error_message="failed",
    )

    mark_failed.assert_awaited_once_with(history_store, "exec-1", "failed")
    repository.mark_run_failed.assert_not_called()
