"""AgentNode message construction tests."""

from __future__ import annotations
from unittest.mock import AsyncMock
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from orcheo.graph.state import State
from orcheo.nodes.ai import AgentNode


@pytest.mark.asyncio
async def test_agentnode_builds_messages_from_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AgentNode should convert ChatKit inputs into LangChain messages."""

    fake_agent = AsyncMock()
    fake_agent.ainvoke.return_value = {"messages": [AIMessage(content="done")]}

    async def fake_prepare_tools(self: AgentNode):  # type: ignore[unused-argument]
        return []

    def fake_init_chat_model(*args, **kwargs):
        return "model"

    def fake_create_agent(model, tools, system_prompt=None, response_format=None):
        return fake_agent

    monkeypatch.setattr("orcheo.nodes.ai.init_chat_model", fake_init_chat_model)
    monkeypatch.setattr("orcheo.nodes.ai.create_agent", fake_create_agent)
    monkeypatch.setattr(AgentNode, "_prepare_tools", fake_prepare_tools)

    node = AgentNode(name="agent", ai_model="test-model", system_prompt="sys-prompt")
    state = State(
        inputs={
            "message": "How can you help?",
            "history": [
                {"role": "assistant", "content": "Welcome back!"},
                {"role": "user", "content": "Remind me what you can do."},
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result == {"messages": [AIMessage(content="done")]}
    payload = fake_agent.ainvoke.await_args.args[0]
    messages = payload["messages"]
    assert isinstance(messages[0], AIMessage)
    assert isinstance(messages[1], HumanMessage)
    assert isinstance(messages[2], HumanMessage)
    assert messages[0].content == "Welcome back!"
    assert messages[1].content == "Remind me what you can do."
    assert messages[2].content == "How can you help?"


@pytest.mark.asyncio
async def test_agentnode_prefers_existing_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit messages should be used when provided."""

    fake_agent = AsyncMock()
    fake_agent.ainvoke.return_value = {"messages": [AIMessage(content="done")]}

    async def fake_prepare_tools(self: AgentNode):  # type: ignore[unused-argument]
        return []

    def fake_init_chat_model(*args, **kwargs):
        return "model"

    def fake_create_agent(model, tools, system_prompt=None, response_format=None):
        return fake_agent

    monkeypatch.setattr("orcheo.nodes.ai.init_chat_model", fake_init_chat_model)
    monkeypatch.setattr("orcheo.nodes.ai.create_agent", fake_create_agent)
    monkeypatch.setattr(AgentNode, "_prepare_tools", fake_prepare_tools)

    node = AgentNode(name="agent", ai_model="test-model")
    state = State(
        messages=[{"role": "user", "content": "Use these messages instead."}],
        inputs={
            "message": "This message should not be appended",
            "history": [{"role": "assistant", "content": "ignored"}],
        },
        results={},
        structured_response=None,
    )

    await node.run(state, {})

    payload = fake_agent.ainvoke.await_args.args[0]
    messages = payload["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "Use these messages instead."
