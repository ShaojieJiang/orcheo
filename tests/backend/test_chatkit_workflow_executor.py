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
from orcheo_backend.app.chatkit.workflow_executor import WorkflowExecutor


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

    def compile(self, checkpointer: object) -> DummyCompiledGraph:
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

    def compile(self, checkpointer: object) -> DummyStreamingCompiledGraph:
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

    final_state = CustomState(
        reply="final reply", messages=[HumanMessage(content="payload")]
    )
    graph = DummyGraph(final_state)

    monkeypatch.setattr(workflow_executor_module, "get_settings", lambda: None)
    monkeypatch.setattr(
        workflow_executor_module,
        "create_checkpointer",
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
    repository.mark_run_succeeded.assert_awaited_once_with(
        run_record.id, actor="chatkit", output={"reply": "final reply"}
    )


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

    steps = [{"node_a": {"value": 1}}, {"node_b": {"value": 2}}]
    final_state = CustomState(
        reply="final reply", messages=[HumanMessage(content="payload")]
    )
    graph = DummyStreamingGraph(steps, final_state)

    monkeypatch.setattr(workflow_executor_module, "get_settings", lambda: None)
    monkeypatch.setattr(
        workflow_executor_module,
        "create_checkpointer",
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
    repository.mark_run_succeeded.assert_awaited_once()
