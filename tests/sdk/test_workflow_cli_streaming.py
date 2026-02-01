"""Tests covering websocket streaming for workflow executions."""

from __future__ import annotations
import json
import sys
from types import ModuleType
from typing import Any, cast
import pytest
from orcheo_sdk.cli import workflow as workflow_module
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.workflow import _stream_workflow_run
from tests.sdk.workflow_cli_test_utils import make_state


@pytest.fixture()
def fake_websockets(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = ModuleType("websockets")
    exceptions_module = ModuleType("websockets.exceptions")

    class InvalidStatusCodeError(Exception):
        def __init__(self, status_code: int) -> None:
            super().__init__(status_code)
            self.status_code = status_code

    class WebSocketExceptionError(Exception):
        pass

    exceptions_module.InvalidStatusCode = InvalidStatusCodeError
    exceptions_module.WebSocketException = WebSocketExceptionError
    module.exceptions = exceptions_module

    def default_connect(*_: Any, **__: Any) -> Any:
        raise RuntimeError("connect stub not configured")

    module.connect = default_connect  # type: ignore[assignment]

    monkeypatch.setitem(sys.modules, "websockets", module)
    monkeypatch.setitem(sys.modules, "websockets.exceptions", exceptions_module)
    return module


@pytest.mark.asyncio()
async def test_stream_workflow_run_includes_additional_headers(
    fake_websockets: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = make_state()

    class DummyConnection:
        async def __aenter__(self) -> DummyConnection:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def send(self, _: str) -> None:
            return None

    connection = DummyConnection()

    def fake_connect(
        uri: str,
        *,
        open_timeout: float,
        close_timeout: float,
        additional_headers: dict[str, str] | None = None,
    ) -> DummyConnection:
        assert uri.endswith("/ws/workflow/wf-1")
        assert open_timeout == 5
        assert close_timeout == 5
        assert additional_headers == {"Authorization": "Bearer token"}
        return connection

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    async def fake_process(_: CLIState, __: Any) -> str:
        return "completed"

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._process_stream_messages", fake_process
    )

    result = await _stream_workflow_run(
        state,
        "wf-1",
        {"nodes": []},
        {"input": "value"},
    )
    assert result == "completed"


@pytest.mark.asyncio()
async def test_stream_workflow_run_falls_back_to_extra_headers(
    fake_websockets: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = make_state()

    class DummyConnection:
        async def __aenter__(self) -> DummyConnection:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def send(self, _: str) -> None:
            return None

    connection = DummyConnection()

    def fake_connect(
        uri: str,
        *,
        open_timeout: float,
        close_timeout: float,
        additional_headers: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> DummyConnection:
        assert uri.endswith("/ws/workflow/wf-1")
        assert open_timeout == 5
        assert close_timeout == 5
        if additional_headers is not None:
            raise TypeError("unexpected keyword argument 'additional_headers'")
        assert extra_headers == {"Authorization": "Bearer token"}
        return connection

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    async def fake_process(_: CLIState, __: Any) -> str:
        return "completed"

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._process_stream_messages", fake_process
    )

    result = await _stream_workflow_run(
        state,
        "wf-1",
        {"nodes": []},
        {"input": "value"},
    )
    assert result == "completed"


@pytest.mark.asyncio()
async def test_stream_workflow_run_without_headers(
    fake_websockets: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = make_state()
    monkeypatch.setattr(state.client, "get_active_token", lambda: None)

    class DummyConnection:
        async def __aenter__(self) -> DummyConnection:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def send(self, _: str) -> None:
            return None

    connection = DummyConnection()

    def fake_connect(
        uri: str,
        *,
        open_timeout: float,
        close_timeout: float,
    ) -> DummyConnection:
        assert uri.endswith("/ws/workflow/wf-1")
        assert open_timeout == 5
        assert close_timeout == 5
        return connection

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    async def fake_process(_: CLIState, __: Any) -> str:
        return "completed"

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._process_stream_messages", fake_process
    )

    result = await _stream_workflow_run(
        state,
        "wf-1",
        {"nodes": []},
        {"input": "value"},
    )
    assert result == "completed"


@pytest.mark.asyncio()
async def test_stream_workflow_run_succeeds(
    fake_websockets: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = make_state()

    class DummyConnection:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def __aenter__(self) -> DummyConnection:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def send(self, message: str) -> None:
            self.sent.append(message)

    connection = DummyConnection()

    async def fake_process(state_arg: CLIState, websocket: Any) -> str:
        assert state_arg is state
        assert websocket is connection
        return "completed"

    def fake_connect(*_: Any, **__: Any) -> DummyConnection:
        return connection

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]
    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._process_stream_messages", fake_process
    )

    result = await _stream_workflow_run(
        state,
        "wf-1",
        {"nodes": []},
        {"input": "value"},
        triggered_by="cli-actor",
        runnable_config={"priority": "high"},
        stored_runnable_config={"tags": ["stored"]},
    )
    assert result == "completed"
    assert connection.sent, "payload was not sent"
    payload = json.loads(connection.sent[0])
    assert payload["type"] == "run_workflow"
    assert payload["inputs"] == {"input": "value"}
    assert payload["triggered_by"] == "cli-actor"
    assert payload["runnable_config"] == {"priority": "high"}
    assert payload["stored_runnable_config"] == {"tags": ["stored"]}


@pytest.mark.asyncio()
async def test_stream_workflow_run_handles_connection_error(
    fake_websockets: ModuleType,
) -> None:
    state = make_state()

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise ConnectionRefusedError("no route")

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await _stream_workflow_run(
        state,
        "wf-1",
        {"cfg": True},
        {},
        triggered_by=None,
    )
    assert result == "connection_error"
    assert any("Failed to connect" in msg for msg in state.console.messages)


@pytest.mark.asyncio()
async def test_stream_workflow_run_handles_timeout(
    fake_websockets: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = make_state()

    class FakeTimeoutError(Exception):
        pass

    monkeypatch.setattr(
        workflow_module, "TimeoutError", FakeTimeoutError, raising=False
    )

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise FakeTimeoutError()

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await _stream_workflow_run(
        state,
        "wf-1",
        {"cfg": True},
        {},
        triggered_by=None,
    )
    assert result == "timeout"
    assert any("Timed out" in msg for msg in state.console.messages)


@pytest.mark.asyncio()
async def test_stream_workflow_run_handles_invalid_status(
    fake_websockets: ModuleType,
) -> None:
    state = make_state()

    invalid_status = cast(
        type[Exception],
        fake_websockets.exceptions.InvalidStatusCode,
    )

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise invalid_status(403)

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await _stream_workflow_run(
        state,
        "wf-1",
        {"cfg": True},
        {},
        triggered_by=None,
    )
    assert result == "http_403"
    assert any("Server rejected connection" in msg for msg in state.console.messages)


@pytest.mark.asyncio()
async def test_stream_workflow_run_handles_websocket_exception(
    fake_websockets: ModuleType,
) -> None:
    state = make_state()

    ws_error = cast(
        type[Exception],
        fake_websockets.exceptions.WebSocketException,
    )

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise ws_error("crash")

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await _stream_workflow_run(
        state,
        "wf-1",
        {"cfg": True},
        {},
        triggered_by=None,
    )
    assert result == "websocket_error"
    assert any("WebSocket error" in msg for msg in state.console.messages)


@pytest.mark.asyncio()
async def test_stream_workflow_evaluation_succeeds(
    fake_websockets: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = make_state()

    class DummyConnection:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def __aenter__(self) -> DummyConnection:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def send(self, message: str) -> None:
            self.sent.append(message)

    connection = DummyConnection()

    async def fake_process(state_arg: CLIState, websocket: Any) -> str:
        assert state_arg is state
        assert websocket is connection
        return "completed"

    def fake_connect(*_: Any, **__: Any) -> DummyConnection:
        return connection

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]
    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._process_stream_messages", fake_process
    )

    result = await workflow_module._stream_workflow_evaluation(
        state,
        "wf-1",
        {"nodes": []},
        {"input": "value"},
        {"name": "agent"},
        triggered_by="cli-actor",
        runnable_config={"priority": "high"},
        stored_runnable_config={"tags": ["stored"]},
    )
    assert result == "completed"
    assert connection.sent, "payload was not sent"
    payload = json.loads(connection.sent[0])
    assert payload["type"] == "evaluate_workflow"
    assert payload["evaluation"] == {"name": "agent"}
    assert payload["runnable_config"] == {"priority": "high"}
    assert payload["stored_runnable_config"] == {"tags": ["stored"]}


@pytest.mark.asyncio()
async def test_stream_workflow_evaluation_handles_connection_error(
    fake_websockets: ModuleType,
) -> None:
    state = make_state()

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise ConnectionRefusedError("no route")

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await workflow_module._stream_workflow_evaluation(
        state,
        "wf-1",
        {"cfg": True},
        {},
        {},
        triggered_by=None,
    )
    assert result == "connection_error"
    assert any("Failed to connect" in msg for msg in state.console.messages)


@pytest.mark.asyncio()
async def test_stream_workflow_evaluation_handles_timeout(
    fake_websockets: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = make_state()

    class FakeTimeoutError(Exception):
        pass

    monkeypatch.setattr(
        workflow_module, "TimeoutError", FakeTimeoutError, raising=False
    )

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise FakeTimeoutError()

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await workflow_module._stream_workflow_evaluation(
        state,
        "wf-1",
        {"cfg": True},
        {},
        {},
        triggered_by=None,
    )
    assert result == "timeout"
    assert any("Timed out" in msg for msg in state.console.messages)


@pytest.mark.asyncio()
async def test_stream_workflow_evaluation_handles_invalid_status(
    fake_websockets: ModuleType,
) -> None:
    state = make_state()

    invalid_status = cast(
        type[Exception],
        fake_websockets.exceptions.InvalidStatusCode,
    )

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise invalid_status(403)

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await workflow_module._stream_workflow_evaluation(
        state,
        "wf-1",
        {"cfg": True},
        {},
        {},
        triggered_by=None,
    )
    assert result == "http_403"
    assert any("Server rejected connection" in msg for msg in state.console.messages)


@pytest.mark.asyncio()
async def test_stream_workflow_evaluation_handles_websocket_exception(
    fake_websockets: ModuleType,
) -> None:
    state = make_state()

    ws_error = cast(
        type[Exception],
        fake_websockets.exceptions.WebSocketException,
    )

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise ws_error("crash")

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await workflow_module._stream_workflow_evaluation(
        state,
        "wf-1",
        {"cfg": True},
        {},
        {},
        triggered_by=None,
    )
    assert result == "websocket_error"
    assert any("WebSocket error" in msg for msg in state.console.messages)
