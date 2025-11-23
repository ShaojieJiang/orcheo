import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.conversation import (
    ConversationCompressorNode,
    ConversationStateNode,
    InMemoryMemoryStore,
    MemorySummarizerNode,
    QueryClarificationNode,
    TopicShiftDetectorNode,
)
from orcheo.nodes.conversational_search.models import ConversationTurn


@pytest.mark.asyncio
async def test_conversation_state_appends_and_limits_history() -> None:
    memory_store = InMemoryMemoryStore()
    node = ConversationStateNode(
        name="conversation_state", memory_store=memory_store, max_turns=2
    )

    await memory_store.save_turn("sess", ConversationTurn(role="user", content="hello"))
    await memory_store.save_turn(
        "sess", ConversationTurn(role="assistant", content="hi there")
    )

    state = State(
        inputs={"session_id": "sess", "user_message": "new message"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["metadata"]["turn_count"] == 3
    assert [turn.content for turn in result["conversation_history"]] == [
        "hello",
        "hi there",
        "new message",
    ][1:]


@pytest.mark.asyncio
async def test_conversation_compressor_summarizes_when_over_budget() -> None:
    turns = [
        ConversationTurn(role="user", content="Tell me about Orcheo"),
        ConversationTurn(role="assistant", content="Orcheo ships graph-native nodes"),
        ConversationTurn(role="user", content="How does the retrieval work?"),
    ]
    state = State(
        inputs={},
        results={"conversation_state": {"conversation_history": turns}},
        structured_response=None,
    )
    node = ConversationCompressorNode(
        name="conversation_compressor", max_tokens=5, summary_max_tokens=4
    )

    result = await node.run(state, {})

    assert result["truncated"] is True
    assert result["conversation_history"][0].metadata["summary"] is True
    assert "Summary:" in result["summary"]


@pytest.mark.asyncio
async def test_topic_shift_detector_flags_low_overlap() -> None:
    history = [
        ConversationTurn(role="user", content="Discuss the retriever architecture"),
        ConversationTurn(role="assistant", content="We use hybrid retrieval"),
    ]
    state = State(
        inputs={"query": "Switching to pricing"},
        results={"conversation_compressor": {"conversation_history": history}},
        structured_response=None,
    )
    node = TopicShiftDetectorNode(name="topic_detector", min_overlap_ratio=0.5)

    result = await node.run(state, {})

    assert result["topic_shift"] is True
    assert result["reason"] == "explicit marker"


@pytest.mark.asyncio
async def test_query_clarification_uses_topic_shift_signal() -> None:
    state = State(
        inputs={"query": "How does it work?"},
        results={"topic_detector": {"topic_shift": True, "last_topic": "retrieval"}},
        structured_response=None,
    )
    node = QueryClarificationNode(name="clarifier")

    result = await node.run(state, {})

    assert result["needs_clarification"] is True
    assert "retrieval" in result["clarifying_question"]


@pytest.mark.asyncio
async def test_memory_summarizer_persists_with_retention() -> None:
    memory_store = InMemoryMemoryStore()
    node = MemorySummarizerNode(
        name="memory_summarizer",
        memory_store=memory_store,
        retention_summaries=2,
    )
    state = State(
        inputs={"session_id": "sess"},
        results={"conversation_compressor": {"summary": "Summary: first"}},
        structured_response=None,
    )

    await node.run(state, {})
    state["results"]["conversation_compressor"] = {"summary": "Summary: second"}
    await node.run(state, {})
    state["results"]["conversation_compressor"] = {"summary": "Summary: third"}
    result = await node.run(state, {})

    session = await memory_store.get_session("sess")

    assert result["summary_count"] == 2
    assert session["summaries"] == ["Summary: second", "Summary: third"]
