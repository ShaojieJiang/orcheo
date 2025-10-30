"""Tests for the ChatKit integration layer."""

from __future__ import annotations
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
import pytest
from chatkit.errors import CustomStreamError
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    InferenceOptions,
    ThreadItemDoneEvent,
    ThreadMetadata,
    UserMessageItem,
    UserMessageTextContent,
)
from fastapi.testclient import TestClient
from orcheo.vault import InMemoryCredentialVault
from orcheo_backend.app import app
from orcheo_backend.app.chatkit_service import (
    ChatKitRequestContext,
    InMemoryChatKitStore,
    create_chatkit_server,
)
from orcheo_backend.app.repository import InMemoryWorkflowRepository


def _build_script_graph() -> dict[str, Any]:
    """Return a LangGraph script that echoes the message as a reply."""
    source = """
from langgraph.graph import END, START, StateGraph

def build_graph():
    graph = StateGraph(dict)

    def respond(state):
        message = state.get("message", "")
        return {"reply": f"Echo: {message}"}

    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    graph.set_entry_point("respond")
    graph.set_finish_point("respond")
    return graph
"""
    return {
        "format": "langgraph_script",
        "source": source,
        "entrypoint": "build_graph",
    }


@pytest.mark.asyncio
async def test_chatkit_server_emits_assistant_reply() -> None:
    """Server streams an assistant message when the workflow produces a reply."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Chat workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    await repository.create_version(
        workflow.id,
        graph=_build_script_graph(),
        metadata={},
        notes=None,
        created_by="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )
    server._run_workflow = AsyncMock(  # type: ignore[attr-defined]
        return_value=("Echo: Ping", {}, None)
    )

    thread = ThreadMetadata(
        id="thr_test",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": str(workflow.id)},
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    user_item = UserMessageItem(
        id="msg_user",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Ping")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item, context)

    events = [event async for event in server.respond(thread, user_item, context)]
    assert len(events) == 1

    event = events[0]
    assert isinstance(event, ThreadItemDoneEvent)
    assert isinstance(event.item, AssistantMessageItem)
    assert "Ping" in event.item.content[0].text


@pytest.mark.asyncio
async def test_chatkit_server_requires_workflow_metadata() -> None:
    """Missing workflow metadata surfaces a descriptive error."""
    repository = InMemoryWorkflowRepository()
    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )
    thread = ThreadMetadata(id="thr_missing", created_at=datetime.now(UTC), metadata={})
    context: ChatKitRequestContext = {}

    user_item = UserMessageItem(
        id="msg_missing",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Hello")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )

    await server.store.save_thread(thread, context)
    await server.store.add_thread_item(thread.id, user_item, context)

    with pytest.raises(CustomStreamError):
        _ = [event async for event in server.respond(thread, user_item, context)]


def test_chatkit_endpoint_rejects_invalid_payload() -> None:
    """FastAPI endpoint returns a 400 for invalid ChatKit payloads."""
    client = TestClient(app)
    response = client.post("/api/chatkit", content="{}")
    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["message"].startswith("Invalid ChatKit payload")


@pytest.mark.asyncio
async def test_in_memory_store_load_threads_pagination() -> None:
    """InMemoryChatKitStore supports paginated thread listing."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    threads = [
        ThreadMetadata(
            id=f"thr_{i}",
            created_at=datetime(2024, 1, i + 1, tzinfo=UTC),
            metadata={"index": i},
        )
        for i in range(5)
    ]
    for thread in threads:
        await store.save_thread(thread, context)

    page1 = await store.load_threads(limit=2, after=None, order="asc", context=context)
    assert len(page1.data) == 2
    assert page1.has_more is True
    assert page1.data[0].id == "thr_0"

    page2 = await store.load_threads(
        limit=2, after=page1.data[-1].id, order="asc", context=context
    )
    assert len(page2.data) == 2
    assert page2.data[0].id == "thr_2"


@pytest.mark.asyncio
async def test_in_memory_store_load_threads_descending() -> None:
    """InMemoryChatKitStore can list threads in descending order."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    for i in range(3):
        thread = ThreadMetadata(
            id=f"thr_{i}",
            created_at=datetime(2024, 1, i + 1, tzinfo=UTC),
        )
        await store.save_thread(thread, context)

    page = await store.load_threads(limit=10, after=None, order="desc", context=context)
    assert page.data[0].id == "thr_2"
    assert page.data[-1].id == "thr_0"


@pytest.mark.asyncio
async def test_in_memory_store_load_thread_items_pagination() -> None:
    """InMemoryChatKitStore supports paginated item listing."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_items"

    items = [
        UserMessageItem(
            id=f"msg_{i}",
            thread_id=thread_id,
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
            content=[UserMessageTextContent(type="input_text", text=f"Message {i}")],
            attachments=[],
            quoted_text=None,
            inference_options=InferenceOptions(),
        )
        for i in range(4)
    ]
    for item in items:
        await store.add_thread_item(thread_id, item, context)

    page1 = await store.load_thread_items(
        thread_id, after=None, limit=2, order="asc", context=context
    )
    assert len(page1.data) == 2
    assert page1.has_more is True

    page2 = await store.load_thread_items(
        thread_id, after=page1.data[-1].id, limit=2, order="asc", context=context
    )
    assert len(page2.data) == 2
    assert page2.has_more is False


@pytest.mark.asyncio
async def test_in_memory_store_save_item() -> None:
    """InMemoryChatKitStore can insert or update items."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_save"

    item = UserMessageItem(
        id="msg_1",
        thread_id=thread_id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Original")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await store.save_item(thread_id, item, context)

    loaded = await store.load_item(thread_id, "msg_1", context)
    assert loaded.content[0].text == "Original"

    updated_item = UserMessageItem(
        id="msg_1",
        thread_id=thread_id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Updated")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await store.save_item(thread_id, updated_item, context)

    loaded_updated = await store.load_item(thread_id, "msg_1", context)
    assert loaded_updated.content[0].text == "Updated"


@pytest.mark.asyncio
async def test_in_memory_store_load_item_not_found() -> None:
    """InMemoryChatKitStore raises NotFoundError for missing items."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    from chatkit.store import NotFoundError

    with pytest.raises(NotFoundError):
        await store.load_item("thr_missing", "msg_missing", context)


@pytest.mark.asyncio
async def test_in_memory_store_delete_thread_item() -> None:
    """InMemoryChatKitStore can delete individual items."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_delete"

    item = UserMessageItem(
        id="msg_delete",
        thread_id=thread_id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Delete me")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await store.add_thread_item(thread_id, item, context)

    await store.delete_thread_item(thread_id, "msg_delete", context)

    page = await store.load_thread_items(
        thread_id, after=None, limit=10, order="asc", context=context
    )
    assert len(page.data) == 0


@pytest.mark.asyncio
async def test_in_memory_store_delete_thread() -> None:
    """InMemoryChatKitStore can delete entire threads."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    thread = ThreadMetadata(id="thr_delete", created_at=datetime.now(UTC))
    await store.save_thread(thread, context)

    await store.delete_thread("thr_delete", context)

    from chatkit.store import NotFoundError

    with pytest.raises(NotFoundError):
        await store.load_thread("thr_delete", context)


@pytest.mark.asyncio
async def test_in_memory_store_attachment_methods_not_implemented() -> None:
    """InMemoryChatKitStore raises NotImplementedError for attachments."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    from chatkit.types import FileAttachment

    attachment = FileAttachment(id="atc_1", name="test.txt", mime_type="text/plain")

    with pytest.raises(NotImplementedError):
        await store.save_attachment(attachment, context)

    with pytest.raises(NotImplementedError):
        await store.load_attachment("atc_1", context)

    with pytest.raises(NotImplementedError):
        await store.delete_attachment("atc_1", context)


@pytest.mark.asyncio
async def test_in_memory_store_merge_metadata_from_context() -> None:
    """InMemoryChatKitStore merges metadata from request context."""
    store = InMemoryChatKitStore()

    class FakeRequest:
        metadata = {"workflow_id": "wf_123", "extra": "data"}

    context: ChatKitRequestContext = {"chatkit_request": FakeRequest()}  # type: ignore[typeddict-item]

    thread = ThreadMetadata(
        id="thr_merge",
        created_at=datetime.now(UTC),
        metadata={"existing": "value"},
    )
    await store.save_thread(thread, context)

    assert thread.metadata["workflow_id"] == "wf_123"
    assert thread.metadata["existing"] == "value"


@pytest.mark.asyncio
async def test_chatkit_server_invalid_workflow_id() -> None:
    """Server raises CustomStreamError for invalid workflow_id format."""
    repository = InMemoryWorkflowRepository()
    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )

    thread = ThreadMetadata(
        id="thr_bad",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": "not-a-uuid"},
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    user_item = UserMessageItem(
        id="msg_bad",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Hello")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item, context)

    with pytest.raises(CustomStreamError, match="invalid"):
        _ = [event async for event in server.respond(thread, user_item, context)]


@pytest.mark.asyncio
async def test_chatkit_server_resolve_user_item_from_history() -> None:
    """Server can resolve the most recent user item when none is provided."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Test workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    await repository.create_version(
        workflow.id,
        graph=_build_script_graph(),
        metadata={},
        notes=None,
        created_by="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )
    server._run_workflow = AsyncMock(return_value=("Reply", {}, None))  # type: ignore[attr-defined]

    thread = ThreadMetadata(
        id="thr_resolve",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": str(workflow.id)},
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    user_item = UserMessageItem(
        id="msg_resolve",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Hello")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item, context)

    events = [event async for event in server.respond(thread, None, context)]
    assert len(events) == 1


@pytest.mark.asyncio
async def test_chatkit_server_resolve_user_item_not_found() -> None:
    """Server raises error when no user item can be found."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Test workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )

    thread = ThreadMetadata(
        id="thr_no_user",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": str(workflow.id)},
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    with pytest.raises(CustomStreamError, match="Unable to locate"):
        _ = [event async for event in server.respond(thread, None, context)]


@pytest.mark.asyncio
async def test_chatkit_server_records_run_metadata() -> None:
    """Server updates thread metadata with run information."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Test workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    await repository.create_version(
        workflow.id,
        graph=_build_script_graph(),
        metadata={},
        notes=None,
        created_by="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )
    server._run_workflow = AsyncMock(  # type: ignore[attr-defined]
        return_value=(
            "Reply",
            {},
            await repository.create_run(
                workflow.id,
                workflow_version_id=(
                    await repository.get_latest_version(workflow.id)
                ).id,
                triggered_by="test",
                input_payload={},
            ),
        )
    )

    thread = ThreadMetadata(
        id="thr_meta",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": str(workflow.id)},
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    user_item = UserMessageItem(
        id="msg_meta",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Test")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item, context)

    _ = [event async for event in server.respond(thread, user_item, context)]

    loaded = await server.store.load_thread(thread.id, context)
    assert "last_run_at" in loaded.metadata
    assert "last_run_id" in loaded.metadata
    assert "runs" in loaded.metadata


@pytest.mark.asyncio
async def test_chatkit_server_workflow_not_found() -> None:
    """Server raises CustomStreamError when workflow doesn't exist."""
    repository = InMemoryWorkflowRepository()
    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )

    from uuid import uuid4

    fake_workflow_id = uuid4()
    thread = ThreadMetadata(
        id="thr_notfound",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": str(fake_workflow_id)},
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    user_item = UserMessageItem(
        id="msg_notfound",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Hello")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item, context)

    with pytest.raises(CustomStreamError):
        _ = [event async for event in server.respond(thread, user_item, context)]


@pytest.mark.asyncio
async def test_chatkit_server_workflow_version_not_found() -> None:
    """Server raises CustomStreamError when workflow version doesn't exist."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Test workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )

    thread = ThreadMetadata(
        id="thr_noversion",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": str(workflow.id)},
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    user_item = UserMessageItem(
        id="msg_noversion",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Hello")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item, context)

    with pytest.raises(CustomStreamError):
        _ = [event async for event in server.respond(thread, user_item, context)]


@pytest.mark.asyncio
async def test_chatkit_server_builds_history() -> None:
    """Server includes conversation history in workflow inputs."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Test workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    await repository.create_version(
        workflow.id,
        graph=_build_script_graph(),
        metadata={},
        notes=None,
        created_by="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )

    captured_inputs = {}

    async def mock_run(wf_id, inputs, actor="chatkit"):
        captured_inputs.update(inputs)
        return ("Reply", {}, None)

    server._run_workflow = AsyncMock(side_effect=mock_run)  # type: ignore[attr-defined]

    thread = ThreadMetadata(
        id="thr_history",
        created_at=datetime.now(UTC),
        metadata={"workflow_id": str(workflow.id)},
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    user_item1 = UserMessageItem(
        id="msg_1",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="First message")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item1, context)

    assistant_item = AssistantMessageItem(
        id="msg_2",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[AssistantMessageContent(text="First response")],
    )
    await server.store.add_thread_item(thread.id, assistant_item, context)

    user_item2 = UserMessageItem(
        id="msg_3",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Second message")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item2, context)

    _ = [event async for event in server.respond(thread, user_item2, context)]

    assert "history" in captured_inputs
    history = captured_inputs["history"]
    assert len(history) == 3
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "First message"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "First response"
    assert history[2]["role"] == "user"
    assert history[2]["content"] == "Second message"


def test_stringify_langchain_message_with_base_message() -> None:
    """_stringify_langchain_message handles BaseMessage objects."""
    from langchain_core.messages import HumanMessage
    from orcheo_backend.app.chatkit_service import _stringify_langchain_message

    msg = HumanMessage(content="Hello world")
    result = _stringify_langchain_message(msg)
    assert result == "Hello world"


def test_stringify_langchain_message_with_mapping() -> None:
    """_stringify_langchain_message handles dict-like objects."""
    from orcheo_backend.app.chatkit_service import _stringify_langchain_message

    msg = {"content": "Test content"}
    result = _stringify_langchain_message(msg)
    assert result == "Test content"

    msg_with_text = {"text": "Test text"}
    result = _stringify_langchain_message(msg_with_text)
    assert result == "Test text"


def test_stringify_langchain_message_with_list() -> None:
    """_stringify_langchain_message handles list content."""
    from langchain_core.messages import HumanMessage
    from orcheo_backend.app.chatkit_service import _stringify_langchain_message

    msg = HumanMessage(content=["Hello", "world"])
    result = _stringify_langchain_message(msg)
    assert result == "Hello world"


def test_stringify_langchain_message_with_nested_list() -> None:
    """_stringify_langchain_message handles nested list structures."""
    from orcheo_backend.app.chatkit_service import _stringify_langchain_message

    msg = {"content": [{"text": "Part 1"}, {"text": "Part 2"}]}
    result = _stringify_langchain_message(msg)
    assert "Part 1" in result
    assert "Part 2" in result


def test_stringify_langchain_message_with_object() -> None:
    """_stringify_langchain_message handles objects with content attribute."""
    from orcheo_backend.app.chatkit_service import _stringify_langchain_message

    class CustomMessage:
        content = "Custom content"

    msg = CustomMessage()
    result = _stringify_langchain_message(msg)
    assert result == "Custom content"


def test_build_initial_state_langgraph_format() -> None:
    """_build_initial_state returns inputs directly for langgraph-script format."""
    from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
    from orcheo_backend.app.chatkit_service import _build_initial_state

    graph_config = {"format": LANGGRAPH_SCRIPT_FORMAT}
    inputs = {"message": "Hello", "metadata": {"key": "value"}}
    result = _build_initial_state(graph_config, inputs)

    assert result == inputs
    assert result["message"] == "Hello"


def test_build_initial_state_standard_format() -> None:
    """_build_initial_state wraps inputs for standard format."""
    from orcheo_backend.app.chatkit_service import _build_initial_state

    graph_config = {"format": "standard"}
    inputs = {"message": "Hello"}
    result = _build_initial_state(graph_config, inputs)

    assert "messages" in result
    assert "results" in result
    assert "inputs" in result
    assert result["inputs"] == inputs


def test_extract_reply_from_state_with_reply_key() -> None:
    """_extract_reply_from_state extracts reply from top-level key."""
    from orcheo_backend.app.chatkit_service import _extract_reply_from_state

    state = {"reply": "Direct reply"}
    result = _extract_reply_from_state(state)
    assert result == "Direct reply"


def test_extract_reply_from_state_with_none_reply() -> None:
    """_extract_reply_from_state handles None reply by checking other locations."""
    from orcheo_backend.app.chatkit_service import _extract_reply_from_state

    state = {"reply": None, "messages": [{"content": "Message content"}]}
    result = _extract_reply_from_state(state)
    assert result is not None


def test_extract_reply_from_state_from_results_dict() -> None:
    """_extract_reply_from_state extracts reply from results mapping."""
    from orcheo_backend.app.chatkit_service import _extract_reply_from_state

    state = {"results": {"node_a": {"reply": "Reply from results"}}}
    result = _extract_reply_from_state(state)
    assert result == "Reply from results"


def test_extract_reply_from_state_from_results_string() -> None:
    """_extract_reply_from_state extracts string value from results."""
    from orcheo_backend.app.chatkit_service import _extract_reply_from_state

    state = {"results": {"node_a": "String result"}}
    result = _extract_reply_from_state(state)
    assert result == "String result"


def test_extract_reply_from_state_from_messages() -> None:
    """_extract_reply_from_state extracts from last message."""
    from langchain_core.messages import AIMessage
    from orcheo_backend.app.chatkit_service import _extract_reply_from_state

    state = {"messages": [AIMessage(content="AI response")]}
    result = _extract_reply_from_state(state)
    assert result == "AI response"


def test_extract_reply_from_state_returns_none() -> None:
    """_extract_reply_from_state returns None when no reply found."""
    from orcheo_backend.app.chatkit_service import _extract_reply_from_state

    state = {"unrelated": "data"}
    result = _extract_reply_from_state(state)
    assert result is None


@pytest.mark.asyncio
async def test_chatkit_server_run_workflow_end_to_end() -> None:
    """_run_workflow executes workflow and returns reply."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Test workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    # Use a properly structured script
    graph_config = {
        "format": "langgraph-script",
        "source": """
from langgraph.graph import END, START, StateGraph

def build_graph():
    graph = StateGraph(dict)

    def respond(state):
        message = state.get("message", "")
        return {"reply": f"Echo: {message}"}

    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph
""",
        "entrypoint": "build_graph",
    }

    await repository.create_version(
        workflow.id,
        graph=graph_config,
        metadata={},
        notes=None,
        created_by="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )

    inputs = {"message": "Test message"}
    reply, state, run = await server._run_workflow(workflow.id, inputs)

    assert reply == "Echo: Test message"
    assert isinstance(state, dict)
    assert run is not None


@pytest.mark.asyncio
async def test_chatkit_server_run_workflow_without_reply() -> None:
    """_run_workflow raises error when workflow doesn't produce reply."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Test workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    # Create a graph that doesn't produce a reply
    graph_config = {
        "format": "langgraph-script",
        "source": """
from langgraph.graph import END, START, StateGraph

def build_graph():
    graph = StateGraph(dict)

    def no_reply(state):
        return {"output": "something else"}

    graph.add_node("no_reply", no_reply)
    graph.add_edge(START, "no_reply")
    graph.add_edge("no_reply", END)
    return graph
""",
        "entrypoint": "build_graph",
    }

    await repository.create_version(
        workflow.id,
        graph=graph_config,
        metadata={},
        notes=None,
        created_by="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )

    with pytest.raises(CustomStreamError, match="without producing a reply"):
        await server._run_workflow(workflow.id, {})


def test_create_chatkit_server_with_default_store() -> None:
    """create_chatkit_server creates SqliteChatKitStore when no store provided."""
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    repository = InMemoryWorkflowRepository()

    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "test_chatkit.sqlite"

        mock_settings = MagicMock()
        mock_settings.get.return_value = str(sqlite_path)
        mock_settings.chatkit_sqlite_path = str(sqlite_path)

        with patch(
            "orcheo_backend.app.chatkit_service.get_settings",
            return_value=mock_settings,
        ):
            server = create_chatkit_server(repository, InMemoryCredentialVault)
            assert server is not None
            assert server._repository == repository


def test_create_chatkit_server_with_env_var() -> None:
    """create_chatkit_server respects CHATKIT_SQLITE_PATH environment variable."""
    import tempfile
    from pathlib import Path
    from unittest.mock import MagicMock, patch

    repository = InMemoryWorkflowRepository()

    with tempfile.TemporaryDirectory() as tmpdir:
        sqlite_path = Path(tmpdir) / "env_chatkit.sqlite"

        mock_settings = MagicMock()
        mock_settings.get.return_value = str(sqlite_path)
        mock_settings.chatkit_sqlite_path = str(sqlite_path)

        with patch(
            "orcheo_backend.app.chatkit_service.get_settings",
            return_value=mock_settings,
        ):
            server = create_chatkit_server(repository, InMemoryCredentialVault)
            assert server is not None


@pytest.mark.asyncio
async def test_in_memory_store_load_thread_items_descending() -> None:
    """InMemoryChatKitStore can list items in descending order."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}
    thread_id = "thr_desc"

    items = [
        UserMessageItem(
            id=f"msg_{i}",
            thread_id=thread_id,
            created_at=datetime(2024, 1, 1, hour=i, tzinfo=UTC),
            content=[UserMessageTextContent(type="input_text", text=f"Message {i}")],
            attachments=[],
            quoted_text=None,
            inference_options=InferenceOptions(),
        )
        for i in range(3)
    ]
    for item in items:
        await store.add_thread_item(thread_id, item, context)

    page = await store.load_thread_items(
        thread_id, after=None, limit=10, order="desc", context=context
    )
    assert page.data[0].id == "msg_2"
    assert page.data[-1].id == "msg_0"


@pytest.mark.asyncio
async def test_collect_text_from_user_content_multiple_parts() -> None:
    """_collect_text_from_user_content joins multiple text parts."""
    from orcheo_backend.app.chatkit_service import _collect_text_from_user_content

    content = [
        UserMessageTextContent(type="input_text", text="Part 1"),
        UserMessageTextContent(type="input_text", text="Part 2"),
    ]
    result = _collect_text_from_user_content(content)
    assert result == "Part 1 Part 2"


@pytest.mark.asyncio
async def test_collect_text_from_assistant_content_multiple_parts() -> None:
    """_collect_text_from_assistant_content joins multiple text parts."""
    from orcheo_backend.app.chatkit_service import _collect_text_from_assistant_content

    content = [
        AssistantMessageContent(text="Response 1"),
        AssistantMessageContent(text="Response 2"),
    ]
    result = _collect_text_from_assistant_content(content)
    assert result == "Response 1 Response 2"


@pytest.mark.asyncio
async def test_chatkit_server_records_run_metadata_with_existing_runs() -> None:
    """Server appends run IDs to existing runs list."""
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Test workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )
    await repository.create_version(
        workflow.id,
        graph=_build_script_graph(),
        metadata={},
        notes=None,
        created_by="tester",
    )

    server = create_chatkit_server(
        repository,
        InMemoryCredentialVault,
        store=InMemoryChatKitStore(),
    )

    run1 = await repository.create_run(
        workflow.id,
        workflow_version_id=(await repository.get_latest_version(workflow.id)).id,
        triggered_by="test",
        input_payload={},
    )

    server._run_workflow = AsyncMock(  # type: ignore[attr-defined]
        return_value=(
            "Reply",
            {},
            await repository.create_run(
                workflow.id,
                workflow_version_id=(
                    await repository.get_latest_version(workflow.id)
                ).id,
                triggered_by="test",
                input_payload={},
            ),
        )
    )

    thread = ThreadMetadata(
        id="thr_runs",
        created_at=datetime.now(UTC),
        metadata={
            "workflow_id": str(workflow.id),
            "runs": [str(run1.id)],
        },
    )
    context: ChatKitRequestContext = {}
    await server.store.save_thread(thread, context)

    user_item = UserMessageItem(
        id="msg_runs",
        thread_id=thread.id,
        created_at=datetime.now(UTC),
        content=[UserMessageTextContent(type="input_text", text="Test")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    await server.store.add_thread_item(thread.id, user_item, context)

    _ = [event async for event in server.respond(thread, user_item, context)]

    loaded = await server.store.load_thread(thread.id, context)
    assert len(loaded.metadata["runs"]) == 2


def test_stringify_langchain_message_with_plain_string() -> None:
    """_stringify_langchain_message handles plain string values."""
    from orcheo_backend.app.chatkit_service import _stringify_langchain_message

    result = _stringify_langchain_message("plain string")
    assert result == "plain string"


def test_stringify_langchain_message_with_none_content() -> None:
    """_stringify_langchain_message handles objects without content."""
    from orcheo_backend.app.chatkit_service import _stringify_langchain_message

    class EmptyMessage:
        pass

    msg = EmptyMessage()
    result = _stringify_langchain_message(msg)
    assert result is not None


@pytest.mark.asyncio
async def test_in_memory_store_merge_metadata_without_request() -> None:
    """InMemoryChatKitStore handles contexts without chatkit_request."""
    store = InMemoryChatKitStore()
    context: ChatKitRequestContext = {}

    thread = ThreadMetadata(
        id="thr_no_request",
        created_at=datetime.now(UTC),
        metadata={"existing": "value"},
    )
    await store.save_thread(thread, context)

    loaded = await store.load_thread("thr_no_request", context)
    assert loaded.metadata["existing"] == "value"
