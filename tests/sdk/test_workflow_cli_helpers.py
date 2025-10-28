"""Additional coverage for workflow CLI helpers."""

from __future__ import annotations
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast
import pytest
from orcheo_sdk.cli import workflow as workflow_module
from orcheo_sdk.cli.config import CLISettings
from orcheo_sdk.cli.errors import CLIError
from orcheo_sdk.cli.state import CLIState
from orcheo_sdk.cli.workflow import (
    _handle_node_event,
    _handle_status_update,
    _process_stream_messages,
    _render_node_output,
    _stream_workflow_run,
    _strip_main_block,
    _upload_langgraph_script,
    run_workflow,
    upload_workflow,
)


class StubConsole:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def print(self, *args: Any, **_: Any) -> None:
        text = " ".join(str(arg) for arg in args)
        self.messages.append(text)


class StubClient:
    def __init__(self) -> None:
        self.base_url = "http://api.test"
        self.responses: dict[str, Any] = {}
        self.calls: list[Any] = []

    def get(self, url: str) -> Any:
        self.calls.append(("GET", url))
        return self.responses[url]

    def post(self, url: str, **payload: Any) -> Any:
        self.calls.append(("POST", url, payload))
        raise NotImplementedError

    def delete(self, url: str) -> None:  # pragma: no cover - not used here
        self.calls.append(("DELETE", url))


def make_state() -> CLIState:
    return CLIState(
        settings=CLISettings(
            api_url="http://api.test",
            service_token="token",
            profile="default",
            offline=False,
        ),
        client=StubClient(),
        cache=object(),
        console=StubConsole(),
    )


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


def test_upload_langgraph_script_fetch_failure() -> None:
    state = make_state()

    class FailingClient(StubClient):
        def get(self, url: str) -> Any:  # type: ignore[override]
            raise RuntimeError("boom")

    state.client = FailingClient()

    workflow_config = {"script": "print('hello')", "entrypoint": None}
    with pytest.raises(CLIError) as excinfo:
        _upload_langgraph_script(
            state,
            workflow_config,
            "wf-1",
            Path("demo.py"),
            None,
        )
    assert "Failed to fetch workflow" in str(excinfo.value)


def test_upload_langgraph_script_create_failure() -> None:
    state = make_state()

    class CreatingClient(StubClient):
        def post(self, url: str, **payload: Any) -> Any:  # type: ignore[override]
            if url.endswith("/api/workflows"):
                raise RuntimeError("cannot create")
            return {"version": 1}

    state.client = CreatingClient()

    workflow_config = {"script": "print('hello')", "entrypoint": None}
    with pytest.raises(CLIError) as excinfo:
        _upload_langgraph_script(
            state,
            workflow_config,
            None,
            Path("demo.py"),
            None,
        )
    assert "Failed to create workflow" in str(excinfo.value)


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
    )
    assert result == "completed"
    assert connection.sent, "payload was not sent"
    payload = json.loads(connection.sent[0])
    assert payload["type"] == "run_workflow"
    assert payload["inputs"] == {"input": "value"}


@pytest.mark.asyncio()
async def test_stream_workflow_run_handles_connection_error(
    fake_websockets: ModuleType,
) -> None:
    state = make_state()

    def fake_connect(*_: Any, **__: Any) -> Any:
        raise ConnectionRefusedError("no route")

    fake_websockets.connect = fake_connect  # type: ignore[attr-defined]

    result = await _stream_workflow_run(state, "wf-1", {"cfg": True}, {})
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

    result = await _stream_workflow_run(state, "wf-1", {"cfg": True}, {})
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

    result = await _stream_workflow_run(state, "wf-1", {"cfg": True}, {})
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

    result = await _stream_workflow_run(state, "wf-1", {"cfg": True}, {})
    assert result == "websocket_error"
    assert any("WebSocket error" in msg for msg in state.console.messages)


@pytest.mark.asyncio()
async def test_process_stream_messages_returns_final_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = make_state()
    updates: list[dict[str, Any]] = []

    def fake_handle(state_arg: CLIState, update: dict[str, Any]) -> str:
        updates.append(update)
        return "completed"

    monkeypatch.setattr("orcheo_sdk.cli.workflow._handle_status_update", fake_handle)

    class FakeWebSocket:
        def __init__(self) -> None:
            self._messages = iter([json.dumps({"status": "completed"})])

        def __aiter__(self) -> FakeWebSocket:
            return self

        async def __anext__(self) -> str:
            try:
                return next(self._messages)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    result = await _process_stream_messages(state, FakeWebSocket())
    assert result == "completed"
    assert updates[0]["status"] == "completed"


@pytest.mark.asyncio()
async def test_process_stream_messages_handles_node_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = make_state()
    handled_events: list[dict[str, Any]] = []

    def fake_status(state_arg: CLIState, update: dict[str, Any]) -> None:
        handled_events.append({"status_checked": update})

    def fake_node_event(state_arg: CLIState, update: dict[str, Any]) -> None:
        handled_events.append(update)

    monkeypatch.setattr("orcheo_sdk.cli.workflow._handle_status_update", fake_status)
    monkeypatch.setattr("orcheo_sdk.cli.workflow._handle_node_event", fake_node_event)

    messages = [
        json.dumps({"status": "running"}),
        json.dumps({"node": "demo", "event": "custom", "payload": {"ok": True}}),
    ]

    class FakeWebSocket:
        def __init__(self, payloads: list[str]) -> None:
            self._payloads = iter(payloads)

        def __aiter__(self) -> FakeWebSocket:
            return self

        async def __anext__(self) -> str:
            try:
                return next(self._payloads)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    result = await _process_stream_messages(state, FakeWebSocket(messages))
    assert result == "completed"
    assert any(event.get("event") == "custom" for event in handled_events)


@pytest.mark.parametrize(
    ("status", "expected", "fragment"),
    [
        ("error", "error", "Error"),
        ("cancelled", "cancelled", "Cancelled"),
        ("completed", "completed", "completed successfully"),
        ("running", None, "Status"),
    ],
)
def test_handle_status_update_variants(
    status: str, expected: str | None, fragment: str
) -> None:
    state = make_state()
    update = {"status": status, "error": "boom", "reason": "user aborted"}
    result = _handle_status_update(state, update)
    if expected is None:
        assert result is None
    else:
        assert result == expected
    assert any(fragment in msg for msg in state.console.messages)


def test_handle_node_event_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    state = make_state()
    outputs: list[Any] = []

    def capture_render(state_arg: CLIState, data: Any) -> None:
        outputs.append(data)

    monkeypatch.setattr("orcheo_sdk.cli.workflow._render_node_output", capture_render)

    _handle_node_event(state, {"node": "A", "event": "on_chain_start"})
    _handle_node_event(
        state,
        {"node": "B", "event": "on_chain_end", "payload": {"value": 1}},
    )
    _handle_node_event(
        state,
        {
            "node": "C",
            "event": "on_chain_error",
            "payload": {"error": "boom"},
        },
    )
    _handle_node_event(
        state,
        {"node": "D", "event": "custom", "payload": {"info": True}},
    )
    _handle_node_event(state, {"node": None, "event": "custom"})

    assert outputs == [{"value": 1}]
    assert any("starting" in msg for msg in state.console.messages)
    assert any("boom" in msg for msg in state.console.messages)
    assert any("[custom]" in msg for msg in state.console.messages)


def test_render_node_output_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    state = make_state()
    rendered: list[Any] = []

    def fake_render_json(console: Any, data: Any, title: Any = None) -> None:
        rendered.append((data, title))

    monkeypatch.setattr("orcheo_sdk.cli.workflow.render_json", fake_render_json)

    _render_node_output(state, None)
    _render_node_output(state, {"a": "b", "c": 1})
    _render_node_output(state, {"a": [1, 2, 3]})
    _render_node_output(state, "short text")
    _render_node_output(state, [1, 2, 3])

    assert any("a='b'" in msg for msg in state.console.messages)
    assert rendered[0][0] == {"a": [1, 2, 3]}
    assert any("[dim]" in msg and "[" in msg for msg in state.console.messages)


def test_run_workflow_raises_on_failed_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    state = make_state()

    state.client.responses = {
        "/api/workflows/wf-1/versions": [
            {"id": "ver-1", "version": 1, "graph": {"nodes": []}}
        ]
    }

    async def fake_stream(
        state_arg: CLIState,
        workflow_id: str,
        graph_config: dict[str, Any],
        inputs: Any,
    ) -> str:
        assert state_arg is state
        assert workflow_id == "wf-1"
        assert graph_config == {"nodes": []}
        assert inputs == {}
        return "error"

    monkeypatch.setattr("orcheo_sdk.cli.workflow._stream_workflow_run", fake_stream)

    class DummyCtx:
        def __init__(self, state_obj: CLIState) -> None:
            self._state = state_obj

        def ensure_object(self, _: Any) -> CLIState:
            return self._state

    with pytest.raises(CLIError) as excinfo:
        run_workflow(DummyCtx(state), "wf-1")
    assert "Workflow execution failed" in str(excinfo.value)


def test_upload_workflow_overrides_entrypoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = make_state()
    dummy_path = tmp_path / "workflow.py"
    dummy_path.write_text("print('hello')", encoding="utf-8")

    loaded_config = {
        "_type": "langgraph_script",
        "script": "print('hello')",
        "entrypoint": None,
    }

    captured_config: dict[str, Any] | None = None

    def fake_loader(path: Path) -> dict[str, Any]:
        assert path == dummy_path
        return dict(loaded_config)

    def fake_uploader(
        state_arg: CLIState,
        workflow_config: dict[str, Any],
        workflow_id: str | None,
        path: Path,
        name_override: str | None,
    ) -> dict[str, Any]:
        nonlocal captured_config
        captured_config = workflow_config
        assert workflow_id is None
        assert path == dummy_path
        assert name_override is None
        return {"id": "wf-123"}

    def fake_render(console: Any, data: Any, title: Any = None) -> None:
        state.console.messages.append(f"render:{data}")

    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._load_workflow_from_python", fake_loader
    )
    monkeypatch.setattr(
        "orcheo_sdk.cli.workflow._upload_langgraph_script", fake_uploader
    )
    monkeypatch.setattr("orcheo_sdk.cli.workflow.render_json", fake_render)

    class DummyCtx:
        def __init__(self, state_obj: CLIState) -> None:
            self._state = state_obj

        def ensure_object(self, _: Any) -> CLIState:
            return self._state

    upload_workflow(
        DummyCtx(state),
        str(dummy_path),
        entrypoint="custom.entry",
    )

    assert captured_config is not None
    assert captured_config["entrypoint"] == "custom.entry"


def test_strip_main_block_stops_on_double_quote() -> None:
    script = "print('hello')\nif __name__ == \"__main__\":\n    run()\nmore()"
    result = _strip_main_block(script)
    assert result == "print('hello')"


def test_strip_main_block_stops_on_single_quote() -> None:
    script = "print('hello')\nif __name__ == '__main__':\n    run()"
    result = _strip_main_block(script)
    assert result == "print('hello')"
