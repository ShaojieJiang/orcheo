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


def test_messages_from_inputs_handles_history_and_prompt() -> None:
    node = AgentNode(name="agent", ai_model="test-model")
    inputs = {
        "history": [
            {"role": "assistant", "content": "Welcome!"},
            "not a mapping",
            {"role": "user", "content": "  "},
            {"role": "user", "content": "Tell me more"},
        ],
        "prompt": "   Add this prompt  ",
    }
    messages = node._messages_from_inputs(inputs)
    assert len(messages) == 3
    assert messages[0].content == "Welcome!"
    assert messages[1].content == "Tell me more"
    assert messages[2].content == "Add this prompt"


def test_normalize_messages_creates_base_messages() -> None:
    node = AgentNode(name="agent", ai_model="test-model")
    inputs = [
        AIMessage(content="existing"),
        {"role": "assistant", "content": "helper"},
        {"role": "other", "content": "fallback"},
        {"role": "user", "content": ""},
        123,
    ]
    normalized = node._normalize_messages(inputs)
    assert len(normalized) == 3
    assert normalized[0].content == "existing"
    assert normalized[1].content == "helper"
    assert normalized[2].content == "fallback"


def test_build_messages_uses_inputs_when_messages_absent() -> None:
    node = AgentNode(name="agent", ai_model="test-model")
    state = State(
        inputs={
            "message": "Fallback message",
            "history": [{"role": "assistant", "content": "Earlier"}],
        },
        results={},
        messages=[],
        structured_response=None,
    )
    messages = node._build_messages(state)
    assert len(messages) == 2
    assert messages[0].content == "Earlier"
    assert messages[1].content == "Fallback message"


def test_messages_from_inputs_prefers_user_message_over_prompt() -> None:
    node = AgentNode(name="agent", ai_model="test-model")
    inputs = {
        "history": [{"role": "assistant", "content": "Old"}],
        "user_message": "  user input  ",
        "prompt": "should be ignored",
    }
    messages = node._messages_from_inputs(inputs)
    assert messages[-1].content == "user input"


def test_messages_from_inputs_handles_query_value() -> None:
    node = AgentNode(name="agent", ai_model="test-model")
    inputs = {
        "query": "  q  ",
    }
    messages = node._messages_from_inputs(inputs)
    assert len(messages) == 1
    assert messages[0].content == "q"


def test_build_messages_prefers_existing_state_messages() -> None:
    node = AgentNode(name="agent", ai_model="test-model")
    state = State(
        messages=[{"role": "assistant", "content": "Existing"}],
        inputs={"message": "ignored"},
        results={},
        structured_response=None,
    )
    messages = node._build_messages(state)
    assert len(messages) == 1
    assert messages[0].content == "Existing"


def test_apply_reset_command_filters_to_latest_reset() -> None:
    node = AgentNode(
        name="agent",
        ai_model="test-model",
        reset_command="RESET",
    )
    messages = [
        HumanMessage(content="before"),
        HumanMessage(content="RESET"),
        HumanMessage(content="after"),
    ]
    trimmed = node._apply_reset_command(messages)
    assert trimmed == messages[1:]


def test_apply_reset_command_returns_original_when_command_missing() -> None:
    node = AgentNode(
        name="agent",
        ai_model="test-model",
        reset_command="RESET",
    )
    messages = [
        HumanMessage(content="keep one"),
        HumanMessage(content="keep two"),
    ]
    assert node._apply_reset_command(messages) == messages


def test_build_messages_respects_max_messages_limit() -> None:
    node = AgentNode(
        name="agent",
        ai_model="test-model",
        max_messages=1,
    )
    state = State(
        messages=[
            {"role": "assistant", "content": "first"},
            {"role": "user", "content": "last"},
        ],
        inputs={},
        results={},
        structured_response=None,
        config=None,
    )
    messages = node._build_messages(state)
    assert len(messages) == 1
    assert messages[0].content == "last"


def test_build_messages_appends_current_input_when_checkpointed() -> None:
    node = AgentNode(name="agent", ai_model="test-model")
    state = State(
        messages=[{"role": "assistant", "content": "Previous answer"}],
        inputs={"message": "New user turn"},
        results={},
        structured_response=None,
        config=None,
    )
    messages = node._build_messages(
        state,
        config={"configurable": {"thread_id": "thread-1", "__pregel_checkpointer": {}}},
    )
    assert len(messages) == 2
    assert messages[0].content == "Previous answer"
    assert messages[1].content == "New user turn"


def test_build_messages_keeps_existing_messages_without_checkpointer() -> None:
    node = AgentNode(name="agent", ai_model="test-model")
    state = State(
        messages=[{"role": "assistant", "content": "Previous answer"}],
        inputs={"message": "Ignored user turn"},
        results={},
        structured_response=None,
        config=None,
    )
    messages = node._build_messages(
        state,
        config={"configurable": {"thread_id": "thread-1"}},
    )
    assert len(messages) == 1
    assert messages[0].content == "Previous answer"


def test_build_messages_checkpointer_with_no_new_inputs() -> None:
    """Checkpointer present but inputs produce no new messages – branch 352->355."""
    node = AgentNode(name="agent", ai_model="test-model")
    state = State(
        messages=[{"role": "assistant", "content": "Previous answer"}],
        inputs={},
        results={},
        structured_response=None,
        config=None,
    )
    messages = node._build_messages(
        state,
        config={"configurable": {"thread_id": "thread-1", "__pregel_checkpointer": {}}},
    )
    assert len(messages) == 1
    assert messages[0].content == "Previous answer"
