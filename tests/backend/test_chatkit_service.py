"""Tests for the ChatKit integration layer."""

from __future__ import annotations
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
import pytest
from chatkit.errors import CustomStreamError
from chatkit.types import (
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
