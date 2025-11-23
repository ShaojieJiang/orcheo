import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search import (
    ConversationCompressorNode,
    ConversationStateNode,
    InMemoryMemoryStore,
    MemorySummarizerNode,
    QueryClarificationNode,
    TopicShiftDetectorNode,
)
from orcheo.nodes.conversational_search.models import ConversationTurn


@pytest.mark.asyncio
async def test_conversation_state_node_appends_and_trims_history() -> None:
    memory_store = InMemoryMemoryStore()
    node = ConversationStateNode(
        name="conversation_state", memory_store=memory_store, max_turns=3
    )

    state = State(
        inputs={"session_id": "sess-1", "user_message": "Hello there"},
        results={},
        structured_response=None,
    )

    first = await node.run(state, {})
    assert len(first["history"]) == 1

    state["inputs"]["user_message"] = "Second turn content"
    second = await node.run(state, {})
    assert len(second["history"]) == 2

    state["inputs"]["user_message"] = "Third turn content"
    _ = await node.run(state, {})
    state["inputs"]["user_message"] = "Fourth turn content"
    trimmed = await node.run(state, {})

    assert len(trimmed["history"]) == 3
    assert trimmed["metadata"]["turn_count"] == 3
    assert trimmed["history"][0].content == "Second turn content"


@pytest.mark.asyncio
async def test_conversation_compressor_respects_token_budget() -> None:
    history = [
        ConversationTurn(role="user", content="Explain Orcheo"),
        ConversationTurn(role="assistant", content="Orcheo provides orchestration"),
        ConversationTurn(role="user", content="Add more details on retrieval"),
    ]
    state = State(
        inputs={},
        results={"conversation_state": {"history": history}},
        structured_response=None,
    )
    compressor = ConversationCompressorNode(
        name="conversation_compressor", max_tokens=5, preserve_recent=1
    )

    result = await compressor.run(state, {})

    assert result["token_count"] <= 5
    assert result["truncated"] is True
    assert len(result["retained_history"]) == 1


@pytest.mark.asyncio
async def test_topic_shift_detector_flags_changes() -> None:
    history = [
        ConversationTurn(role="user", content="Tell me about climate change"),
        ConversationTurn(role="assistant", content="It affects weather patterns."),
    ]
    state = State(
        inputs={"query": "Switching topics, let's discuss jazz music"},
        results={"conversation_state": {"history": history}},
        structured_response=None,
    )
    detector = TopicShiftDetectorNode(
        name="topic_shift_detector", similarity_threshold=0.4
    )

    result = await detector.run(state, {})

    assert result["topic_shift"] is True
    assert result["similarity"] < 0.4


@pytest.mark.asyncio
async def test_query_clarification_node_builds_prompt() -> None:
    state = State(
        inputs={"query": "it"},
        results={"topic_shift_detector": {"topic_shift": False}},
        structured_response=None,
    )
    clarifier = QueryClarificationNode(name="query_clarifier", min_query_words=3)

    result = await clarifier.run(state, {})

    assert result["needs_clarification"] is True
    assert "detail" in result["prompt"]


@pytest.mark.asyncio
async def test_memory_summarizer_persists_entries_with_retention() -> None:
    memory_store = InMemoryMemoryStore()
    history = [
        ConversationTurn(role="user", content="Hello"),
        ConversationTurn(role="assistant", content="Hi there"),
        ConversationTurn(role="user", content="Tell me more"),
    ]
    state = State(
        inputs={"session_id": "sess-memory"},
        results={
            "conversation_state": {"history": history},
            "conversation_compressor": {"summary": "user and assistant talked"},
        },
        structured_response=None,
    )
    summarizer = MemorySummarizerNode(
        name="memory_summarizer", memory_store=memory_store, retention_count=1
    )

    first = await summarizer.run(state, {})
    assert len(first["retained"]) == 1

    state["results"]["conversation_compressor"]["summary"] = "updated summary"
    second = await summarizer.run(state, {})

    assert len(second["retained"]) == 1
    assert second["retained"][0].summary == "updated summary"


@pytest.mark.asyncio
async def test_multi_turn_flow_integration() -> None:
    memory_store = InMemoryMemoryStore()
    conversation_state = ConversationStateNode(
        name="conversation_state", memory_store=memory_store, max_turns=5
    )
    compressor = ConversationCompressorNode(name="conversation_compressor")
    detector = TopicShiftDetectorNode(name="topic_shift_detector")
    clarifier = QueryClarificationNode(name="query_clarifier")
    summarizer = MemorySummarizerNode(
        name="memory_summarizer", memory_store=memory_store, retention_count=2
    )

    state = State(
        inputs={"session_id": "sess-flow", "user_message": "Tell me about Orcheo"},
        results={},
        structured_response=None,
    )

    convo_result = await conversation_state.run(state, {})
    state["results"][conversation_state.name] = convo_result

    state["inputs"]["user_message"] = "How does pricing work?"
    convo_result = await conversation_state.run(state, {})
    state["results"][conversation_state.name] = convo_result

    compression_result = await compressor.run(state, {})
    state["results"][compressor.name] = compression_result

    state["inputs"]["query"] = "Switching topics, recommend some music"
    topic_result = await detector.run(state, {})
    state["results"][detector.name] = topic_result

    clarification_result = await clarifier.run(state, {})
    state["results"][clarifier.name] = clarification_result

    summary_result = await summarizer.run(state, {})

    assert topic_result["topic_shift"] is True
    assert clarification_result["needs_clarification"] is True
    assert summary_result["retained"]
    assert len(summary_result["retained"]) <= 2
