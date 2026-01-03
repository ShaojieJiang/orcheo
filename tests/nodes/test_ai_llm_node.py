"""LLMNode message construction tests."""

from __future__ import annotations
from unittest.mock import AsyncMock
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from orcheo.graph.state import State
from orcheo.nodes.ai import LLMNode


@pytest.mark.asyncio
async def test_llmnode_run_builds_single_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLMNode should wrap input text and instruction into one message."""

    fake_agent = AsyncMock()
    fake_agent.ainvoke.return_value = {"messages": [AIMessage(content="done")]}

    async def fake_prepare_tools(self: LLMNode):  # type: ignore[unused-argument]
        return []

    def fake_init_chat_model(*args, **kwargs):
        return "model"

    def fake_create_agent(model, tools, system_prompt=None, response_format=None):
        return fake_agent

    monkeypatch.setattr("orcheo.nodes.ai.init_chat_model", fake_init_chat_model)
    monkeypatch.setattr("orcheo.nodes.ai.create_agent", fake_create_agent)
    monkeypatch.setattr(LLMNode, "_prepare_tools", fake_prepare_tools)

    node = LLMNode(
        name="llm",
        ai_model="test-model",
        user_message="Bonjour",
        draft_reply="Hello there",
        instruction="Translate to French",
    )
    state = State(inputs={}, results={}, structured_response=None)

    result = await node.run(state, {})

    assert result == {"messages": [AIMessage(content="done")]}
    payload = fake_agent.ainvoke.await_args.args[0]
    messages = payload["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == (
        "Instruction:\nTranslate to French\n\nText:\nUser message:\nBonjour\n\n"
        "Draft reply:\nHello there"
    )


def test_llmnode_build_messages_skips_empty_input() -> None:
    node = LLMNode(name="llm", ai_model="test-model", input_text="  ")
    state = State(inputs={}, results={}, structured_response=None)
    assert node._build_messages(state) == []
