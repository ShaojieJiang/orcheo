import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.conversation import (
    ConversationCompressorNode,
    ConversationStateNode,
    MemorySummarizerNode,
    QueryClarificationNode,
    TopicShiftDetectorNode,
)
from orcheo.nodes.conversational_search.memory import InMemoryMemoryStore


@pytest.mark.asyncio
async def test_conversation_state_appends_messages_and_bounds_turns() -> None:
    node = ConversationStateNode(name="conversation_state", max_turns=2)
    state = State(
        inputs={
            "session_id": "sess-1",
            "history": [
                {"role": "user", "content": "Tell me about retrievers."},
                {"role": "assistant", "content": "They combine vector and BM25."},
            ],
            "user_message": "What about hybrid?",
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["metadata"]["turn_count"] == 2
    assert result["conversation_history"][-1].content == "What about hybrid?"


@pytest.mark.asyncio
async def test_conversation_compressor_limits_tokens_and_summarizes() -> None:
    node = ConversationCompressorNode(name="compressor", max_tokens=5)
    state = State(
        inputs={
            "conversation_history": [
                {"role": "user", "content": "Explain vector search."},
                {"role": "assistant", "content": "It uses embeddings."},
                {"role": "user", "content": "Also BM25."},
            ]
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["truncated"] is True
    assert "user: Also BM25." in result["summary"]
    assert result["total_tokens"] <= 5


@pytest.mark.asyncio
async def test_topic_shift_detector_flags_low_overlap() -> None:
    node = TopicShiftDetectorNode(name="topic_shift")
    state = State(
        inputs={
            "query": "Tell me pricing tiers",
            "conversation_history": [
                {"role": "user", "content": "Explain vector stores"},
                {"role": "assistant", "content": "They index embeddings."},
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["topic_shift"] is True
    assert 0 <= result["overlap"] <= 1


@pytest.mark.asyncio
async def test_query_clarification_respects_topic_signal() -> None:
    node = QueryClarificationNode(name="clarifier")
    state = State(
        inputs={"query": "More"},
        results={"topic_shift": {"topic_shift": True}},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["needs_clarification"] is True
    assert "clarify" in result["clarification_prompt"].lower()


@pytest.mark.asyncio
async def test_memory_summarizer_persists_with_retention() -> None:
    store = InMemoryMemoryStore(max_turns=2)
    node = MemorySummarizerNode(
        name="memory",
        memory_store=store,
        max_turns=2,
        retention_tokens=10,
    )
    state = State(
        inputs={
            "session_id": "sess-2",
            "conversation_history": [
                {"role": "user", "content": "First question"},
                {"role": "assistant", "content": "First answer"},
                {"role": "user", "content": "Second question"},
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    history = await store.get_history("sess-2", limit=10)
    assert len(history) == 2
    assert result["persisted_turns"] == 2
    assert "user: Second question" in result["summary"]
