"""Tests for ChatKit server helpers that parse widget payloads and route actions."""

from __future__ import annotations
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
import pytest
from chatkit.errors import CustomStreamError
from chatkit.store import Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    NoticeEvent,
    ThreadItemDoneEvent,
    ThreadMetadata,
    WidgetItem,
)
from dynaconf import Dynaconf
from orcheo_backend.app.chatkit import server as server_module
from orcheo_backend.app.chatkit.context import ChatKitRequestContext
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)


class DummyStore(Store[ChatKitRequestContext]):
    """Minimal store implementation used by the server helpers."""

    def __init__(self) -> None:
        self.generated: list[str] = []
        self.saved: list[str] = []
        self.added: list[tuple[str, Any]] = []

    def generate_item_id(
        self,
        item_type: str,
        thread: ThreadMetadata,
        context: ChatKitRequestContext,
    ) -> str:
        identifier = f"{item_type}-{len(self.generated) + 1}"
        self.generated.append(identifier)
        return identifier

    async def load_thread(self, _, __):
        raise NotImplementedError

    async def save_thread(self, thread_id: str, context: ChatKitRequestContext) -> None:
        self.saved.append(thread_id)

    async def load_thread_items(self, *args, **kwargs):
        raise NotImplementedError

    async def save_attachment(self, *args, **kwargs):
        raise NotImplementedError

    async def load_attachment(self, *args, **kwargs):
        raise NotImplementedError

    async def delete_attachment(self, *args, **kwargs):
        raise NotImplementedError

    async def load_threads(self, *args, **kwargs):
        raise NotImplementedError

    async def add_thread_item(
        self, thread_id: str, item: Any, context: ChatKitRequestContext
    ) -> None:
        self.added.append((thread_id, item))

    async def save_item(self, *args, **kwargs):
        raise NotImplementedError

    async def load_item(self, *args, **kwargs):
        raise NotImplementedError

    async def delete_thread(self, *args, **kwargs):
        raise NotImplementedError

    async def delete_thread_item(self, *args, **kwargs):
        raise NotImplementedError


def create_server() -> tuple[server_module.OrcheoChatKitServer, DummyStore]:
    store = DummyStore()
    repository = Mock()
    server = server_module.OrcheoChatKitServer(
        store=store,
        repository=repository,
        vault_provider=lambda: None,
    )
    return server, store


def test_action_type_for_logging_handles_mapping_and_attributes() -> None:
    mapping = {"type": "map"}
    assert server_module._action_type_for_logging(mapping) == "map"

    class ActionObject:
        type = "object"

    assert server_module._action_type_for_logging(ActionObject()) == "object"


def test_candidate_type_reads_from_mapping_and_attributes() -> None:
    assert server_module._candidate_type({"type": "Card"}) == "Card"

    class Candidate:
        type = "ListView"

    assert server_module._candidate_type(Candidate()) == "ListView"


def test_content_text_extracts_from_strings_and_lists() -> None:
    assert server_module._content_text("plain") == "plain"

    mixed = [
        {"text": "first"},
        SimpleNamespace(text="second"),
        {"content": "ignored"},
    ]
    assert server_module._content_text(mixed) == "first"
    assert server_module._content_text([SimpleNamespace(nontext=1)]) is None


def test_content_text_uses_attribute_fallback() -> None:
    entries = [
        {"content": "ignored"},
        SimpleNamespace(text="attr text"),
    ]
    assert server_module._content_text(entries) == "attr text"


def test_candidate_from_content_handles_invalid_json() -> None:
    assert server_module._candidate_from_content("not-json", None) is None


def test_candidate_from_content_rejects_non_widget_types() -> None:
    assert server_module._candidate_from_content('{"type": "Unknown"}', "copy") is None


def test_candidate_from_content_builds_widget_candidate() -> None:
    candidate = server_module._candidate_from_content(
        '{"type": "Card"}', copy_text="copy"
    )
    assert candidate is not None
    assert candidate.payload["type"] == "Card"
    assert candidate.copy_text == "copy"


def test_candidate_from_content_rejects_unknown_types() -> None:
    assert server_module._candidate_from_content('{"type": "Unknown"}', None) is None
    assert server_module._candidate_from_content("not json", None) is None


def test_candidate_from_artifact_returns_structured_content() -> None:
    artifact = {
        "structured_content": {"type": "ListView"},
        "copy_text": "copy",
    }
    candidate = server_module._candidate_from_artifact(artifact)
    assert candidate is not None
    assert candidate.payload["type"] == "ListView"
    assert candidate.copy_text == "copy"


def test_extract_widget_candidate_prefers_artifact() -> None:
    message = {
        "artifact": {
            "structured_content": {"type": "Card"},
            "copy_text": "text",
        },
        "content": '{"type": "ListView"}',
    }
    candidate = server_module._extract_widget_candidate(message)
    assert candidate is not None
    assert candidate.payload["type"] == "Card"
    assert candidate.copy_text == "text"


def test_extract_widget_candidate_falls_back_to_content() -> None:
    message = {"content": '{"type": "Card"}'}
    candidate = server_module._extract_widget_candidate(message)
    assert candidate is not None
    assert candidate.payload["type"] == "Card"


def test_extract_widget_candidate_accepts_artifact_without_type() -> None:
    message = {
        "artifact": {
            "structured_content": {},
            "copy_text": "no-type",
        }
    }
    candidate = server_module._extract_widget_candidate(message)
    assert candidate is not None
    assert candidate.payload == {}
    assert candidate.copy_text == "no-type"


def test_validate_widget_root_rejects_missing_type() -> None:
    with pytest.raises(server_module._WidgetHydrationError):
        server_module._validate_widget_root({"content": "no type"})


def test_validate_widget_root_rejects_large_payload() -> None:
    payload = {"type": "Card", "title": "x" * 100_000}
    with pytest.raises(server_module._WidgetHydrationError) as excinfo:
        server_module._validate_widget_root(payload)
    assert excinfo.value.reason == "too_large"


def test_notice_for_widget_error_variants() -> None:
    large_error = server_module._WidgetHydrationError(
        "too_large", detail="big", size_bytes=60_000
    )
    result = server_module._notice_for_widget_error(large_error)
    assert "too large" in result.message

    missing_error = server_module._WidgetHydrationError("invalid_widget")
    notice = server_module._notice_for_widget_error(missing_error)
    assert (
        notice.message == "The workflow returned a widget that could not be rendered."
    )


def test_hydrate_widget_items_returns_widget_and_notices() -> None:
    server, store = create_server()
    thread = ThreadMetadata(
        id="thread",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "workflow"},
    )
    context: ChatKitRequestContext = {}
    message = {"type": "tool", "content": '{"type": "Card"}'}
    widget_items, notices = server._hydrate_widget_items(
        thread, {"_messages": [message]}, context
    )
    assert len(widget_items) == 1
    assert not notices

    # Invalid payload should produce a notice
    invalid_message = {
        "type": "tool",
        "artifact": {"structured_content": {"foo": "bar"}},
    }
    widget_items, notices = server._hydrate_widget_items(
        thread, {"_messages": [invalid_message]}, context
    )
    assert widget_items == []
    assert notices


def test_hydrate_widget_items_skips_non_tool_messages() -> None:
    server, store = create_server()
    thread = ThreadMetadata(
        id="thread",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "workflow"},
    )
    context: ChatKitRequestContext = {}
    widget_items, notices = server._hydrate_widget_items(
        thread, {"_messages": [{"type": "not_tool"}]}, context
    )
    assert widget_items == []
    assert notices == []


def test_resolve_chatkit_sqlite_path_uses_dynaconf_and_mappings() -> None:
    dynaconf = Dynaconf(settings_files=[], load_dotenv=False)
    dynaconf.set("CHATKIT_SQLITE_PATH", "~/dynaconf.sqlite")
    dynaconf_path = server_module._resolve_chatkit_sqlite_path(dynaconf)
    assert dynaconf_path == server_module.Path("~/dynaconf.sqlite").expanduser()

    mapping_path = server_module._resolve_chatkit_sqlite_path(
        {"CHATKIT_SQLITE_PATH": "~/map.sqlite"}
    )
    assert mapping_path == server_module.Path("~/map.sqlite").expanduser()

    class ConfigObject:
        chatkit_sqlite_path = "~/attr.sqlite"

    object_path = server_module._resolve_chatkit_sqlite_path(ConfigObject())
    assert object_path == server_module.Path("~/attr.sqlite").expanduser()

    default_path = server_module._resolve_chatkit_sqlite_path(object())
    assert default_path == server_module.Path("~/.orcheo/chatkit.sqlite").expanduser()


def test_workflow_id_from_thread_reads_metadata() -> None:
    thread = ThreadMetadata(
        id="thread",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "id"},
    )
    assert server_module._workflow_id_from_thread(thread) == "id"

    thread.metadata = {}
    assert server_module._workflow_id_from_thread(thread) is None


def test_is_tool_message_recognises_tool_types() -> None:
    assert server_module._is_tool_message({"type": "tool"})

    class ToolLike:
        type = "tool"

    assert not server_module._is_tool_message(ToolLike())
    assert not server_module._is_tool_message({"type": "other"})


@pytest.mark.asyncio
async def test_action_handles_workflow_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, store = create_server()
    thread = ThreadMetadata(
        id="thread-not-found",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "wf"},
    )
    monkeypatch.setattr(server, "_ensure_workflow_metadata", lambda *_: None)
    monkeypatch.setattr(server, "_require_workflow_id", lambda *_: uuid4())
    monkeypatch.setattr(server, "_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        server_module,
        "build_action_inputs_payload",
        lambda *_: {"payload": "value"},
    )
    mock_failure = AsyncMock(side_effect=WorkflowNotFoundError("missing"))
    monkeypatch.setattr(server, "_run_workflow", mock_failure)
    log_mock = Mock()
    server._log_action_failure = log_mock

    with pytest.raises(CustomStreamError):
        async for _ in server.action(thread, {"type": "submit"}, None, {}):
            ...
    assert log_mock.called


@pytest.mark.asyncio
async def test_action_handles_version_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, store = create_server()
    thread = ThreadMetadata(
        id="thread-version",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "wf"},
    )
    monkeypatch.setattr(server, "_ensure_workflow_metadata", lambda *_: None)
    monkeypatch.setattr(server, "_require_workflow_id", lambda *_: uuid4())
    monkeypatch.setattr(server, "_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        server_module,
        "build_action_inputs_payload",
        lambda *_: {"payload": "value"},
    )
    mock_failure = AsyncMock(side_effect=WorkflowVersionNotFoundError("version"))
    monkeypatch.setattr(server, "_run_workflow", mock_failure)
    server._log_action_failure = Mock()

    with pytest.raises(CustomStreamError):
        async for _ in server.action(thread, {"type": "submit"}, None, {}):
            ...
    assert server._log_action_failure.called


@pytest.mark.asyncio
async def test_action_logs_and_reraises_generic_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, store = create_server()
    thread = ThreadMetadata(
        id="thread-error",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "wf"},
    )
    monkeypatch.setattr(server, "_ensure_workflow_metadata", lambda *_: None)
    monkeypatch.setattr(server, "_require_workflow_id", lambda *_: uuid4())
    monkeypatch.setattr(server, "_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        server_module,
        "build_action_inputs_payload",
        lambda *_: {"payload": "value"},
    )
    mock_failure = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(server, "_run_workflow", mock_failure)
    log_mock = Mock()
    server._log_action_failure = log_mock

    with pytest.raises(RuntimeError):
        async for _ in server.action(thread, {"type": "submit"}, None, {}):
            ...
    assert log_mock.called


@pytest.mark.asyncio
async def test_action_streams_widgets_and_assistant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, store = create_server()
    thread = ThreadMetadata(
        id="thread-stream",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "wf"},
    )
    context: ChatKitRequestContext = {"actor": "actor"}
    monkeypatch.setattr(server, "_ensure_workflow_metadata", lambda *_: None)
    monkeypatch.setattr(server, "_require_workflow_id", lambda *_: uuid4())
    monkeypatch.setattr(server, "_history", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        server_module,
        "build_action_inputs_payload",
        lambda *_: {"payload": "value"},
    )

    async def fake_run_workflow(*args: Any, **kwargs: Any):
        return "reply", {}, None

    monkeypatch.setattr(server, "_run_workflow", fake_run_workflow)
    notice = NoticeEvent(level="info", message="note")
    widget_item = WidgetItem(
        id="widget",
        thread_id="thread-stream",
        created_at=datetime.now(UTC),
        widget={"type": "Card"},
    )
    monkeypatch.setattr(
        server,
        "_hydrate_widget_items",
        lambda *_: ([widget_item], [notice]),
    )
    assistant_item = AssistantMessageItem(
        id="assistant",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[AssistantMessageContent(text="reply")],
    )
    monkeypatch.setattr(server, "_build_assistant_item", lambda *_: assistant_item)
    store.add_thread_item = AsyncMock()
    store.save_thread = AsyncMock()
    events: list[Any] = []
    async for event in server.action(thread, {"type": "submit"}, None, context):
        events.append(event)

    assert events[0] is notice
    assert isinstance(events[1], ThreadItemDoneEvent)
    assert events[1].item is widget_item
    assert isinstance(events[2], ThreadItemDoneEvent)
    store.add_thread_item.assert_any_await(thread.id, widget_item, context)
    store.add_thread_item.assert_any_await(thread.id, assistant_item, context)
    store.save_thread.assert_awaited_once_with(thread, context)
