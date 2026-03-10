"""Tests for workflow credential readiness helpers and endpoint."""

from __future__ import annotations
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from orcheo_backend.app import get_workflow_credential_readiness
from orcheo_backend.app.credential_readiness import (
    collect_workflow_credential_placeholders,
)
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)


def test_collect_workflow_credential_placeholders_scans_nested_tool_graphs() -> None:
    source = """
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode
from orcheo.nodes.telegram import MessageTelegram

class TelegramInput(BaseModel):
    message: str = Field(description="Message to send")

def build_tool_graph() -> StateGraph:
    graph = StateGraph(State)
    graph.add_node(
        "send_telegram",
        MessageTelegram(
            name="send_telegram",
            chat_id="{{config.configurable.telegram_chat_id}}",
            message="{{inputs.message}}",
        ),
    )
    graph.add_edge(START, "send_telegram")
    graph.add_edge("send_telegram", END)
    return graph

def orcheo_workflow() -> StateGraph:
    graph = StateGraph(State)
    agent = AgentNode(
        name="agent",
        ai_model="openai:gpt-4o-mini",
        model_kwargs={"api_key": "[[openai_api_key]]"},
        workflow_tools=[
            {
                "name": "send_telegram_message",
                "description": "Send a Telegram message.",
                "graph": build_tool_graph(),
                "args_schema": TelegramInput,
            }
        ],
    )
    graph.add_node("agent", agent)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph
"""

    placeholders = collect_workflow_credential_placeholders(
        {"source": source, "entrypoint": None},
        {"configurable": {"telegram_chat_id": "[[telegram_chat_id]]"}},
    )

    assert sorted(placeholders) == [
        "openai_api_key",
        "telegram_chat_id",
        "telegram_token",
    ]
    assert placeholders["telegram_token"] == {"[[telegram_token]]"}


def test_collect_workflow_credential_placeholders_falls_back_when_source_fails() -> (
    None
):
    placeholders = collect_workflow_credential_placeholders(
        {
            "source": """
def orcheo_workflow():
    raise RuntimeError("boom")
""",
            "entrypoint": None,
            "nodes": [{"token": "[[slack_bot_token]]"}],
        },
        {"configurable": {"fallback_token": "[[fallback_token]]"}},
    )

    assert placeholders == {
        "fallback_token": {"[[fallback_token]]"},
        "slack_bot_token": {"[[slack_bot_token]]"},
    }


def test_collect_workflow_credential_placeholders_raw_payloads_no_source() -> None:
    placeholders = collect_workflow_credential_placeholders(
        {"nodes": [{"token": "[[slack_bot_token]]"}]},
        None,
    )

    assert placeholders == {"slack_bot_token": {"[[slack_bot_token]]"}}


@pytest.mark.asyncio()
async def test_get_workflow_credential_readiness_handles_missing_workflow() -> None:
    class Repository:
        async def resolve_workflow_ref(self, workflow_ref, *, include_archived=True):
            del include_archived
            return UUID(str(workflow_ref))

        async def get_workflow(self, workflow_id):
            raise WorkflowNotFoundError(str(workflow_id))

    class Vault:
        def list_credentials(self, context):
            del context
            return []

    with pytest.raises(HTTPException) as exc_info:
        await get_workflow_credential_readiness(
            str(uuid4()),
            repository=Repository(),
            vault=Vault(),
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio()
async def test_get_workflow_credential_readiness_without_versions() -> None:
    workflow_id = uuid4()

    class Repository:
        async def resolve_workflow_ref(self, workflow_ref, *, include_archived=True):
            del workflow_ref, include_archived
            return workflow_id

        async def get_workflow(self, workflow_id):
            return object()

        async def get_latest_version(self, workflow_id):
            raise WorkflowVersionNotFoundError(str(workflow_id))

    class Vault:
        def list_credentials(self, context):
            del context
            return []

    response = await get_workflow_credential_readiness(
        str(workflow_id),
        repository=Repository(),
        vault=Vault(),
    )

    assert response.status == "not_required"
    assert response.referenced_credentials == []


@pytest.mark.asyncio()
async def test_get_workflow_credential_readiness_reports_available_and_missing() -> (
    None
):
    workflow_id = uuid4()
    version = SimpleNamespace(
        graph={
            "source": """
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode
from orcheo.nodes.telegram import MessageTelegram

class TelegramInput(BaseModel):
    message: str = Field(description="Message to send")

def build_tool_graph() -> StateGraph:
    graph = StateGraph(State)
    graph.add_node(
        "send_telegram",
        MessageTelegram(
            name="send_telegram",
            chat_id="{{config.configurable.telegram_chat_id}}",
            message="{{inputs.message}}",
        ),
    )
    graph.add_edge(START, "send_telegram")
    graph.add_edge("send_telegram", END)
    return graph

def orcheo_workflow() -> StateGraph:
    graph = StateGraph(State)
    agent = AgentNode(
        name="agent",
        ai_model="openai:gpt-4o-mini",
        model_kwargs={"api_key": "[[openai_api_key]]"},
        workflow_tools=[
            {
                "name": "send_telegram_message",
                "description": "Send a Telegram message.",
                "graph": build_tool_graph(),
                "args_schema": TelegramInput,
            }
        ],
    )
    graph.add_node("agent", agent)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", END)
    return graph
""",
            "entrypoint": None,
        },
        runnable_config={"configurable": {"telegram_chat_id": "[[telegram_chat_id]]"}},
    )

    class Repository:
        async def resolve_workflow_ref(self, workflow_ref, *, include_archived=True):
            del workflow_ref, include_archived
            return workflow_id

        async def get_workflow(self, workflow_id):
            return object()

        async def get_latest_version(self, workflow_id):
            return version

    class Vault:
        def list_credentials(self, context):
            del context
            return [
                SimpleNamespace(
                    id=uuid4(),
                    name="openai_api_key",
                    provider="openai",
                ),
                SimpleNamespace(
                    id=uuid4(),
                    name="telegram_token",
                    provider="telegram",
                ),
            ]

    response = await get_workflow_credential_readiness(
        str(workflow_id),
        repository=Repository(),
        vault=Vault(),
    )

    assert response.status == "missing"
    assert response.available_credentials == ["openai_api_key", "telegram_token"]
    assert response.missing_credentials == ["telegram_chat_id"]
