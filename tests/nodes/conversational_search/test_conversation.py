import time

import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.conversation import (
    ConversationCompressorNode,
    ConversationStateNode,
    InMemoryMemoryStore,
    MemorySummarizerNode,
    MemoryTurn,
    QueryClarificationNode,
    TopicShiftDetectorNode,
)


@pytest.mark.asyncio
async def test_conversation_state_appends_and_limits_history() -> None:
    store = InMemoryMemoryStore()
    node = ConversationStateNode(
        name="conversation_state", memory_store=store, max_turns=2
    )

    state = State(
        inputs={"session_id": "sess-1", "user_message": "Hello"},
        results={},
        structured_response=None,
    )

    first_result = await node.run(state, {})
    assert first_result["turn_count"] == 1

    state["inputs"]["user_message"] = "Second turn"
    await node.run(state, {})
    state["inputs"]["user_message"] = "Third turn"
    final_result = await node.run(state, {})

    assert final_result["turn_count"] == 2
    assert [turn["content"] for turn in final_result["conversation_history"]] == [
        "Second turn",
        "Third turn",
    ]
    assert final_result["truncated"] is True


@pytest.mark.asyncio
async def test_conversation_state_prunes_existing_history() -> None:
    store = InMemoryMemoryStore()
    await store.append_turn("sess-prune", MemoryTurn(role="user", content="first"))
    await store.append_turn(
        "sess-prune", MemoryTurn(role="assistant", content="second")
    )
    node = ConversationStateNode(
        name="conversation_state", memory_store=store, max_turns=2
    )

    state = State(
        inputs={"session_id": "sess-prune", "user_message": "newest"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["turn_count"] == 2
    assert result["conversation_history"][-1]["content"] == "newest"


@pytest.mark.asyncio
async def test_conversation_compressor_summarizes_history() -> None:
    node = ConversationCompressorNode(
        name="compressor", max_tokens=4, preserve_recent=1, source_result_key="state"
    )
    state = State(
        inputs={},
        results={
            "state": {
                "conversation_history": [
                    {"role": "user", "content": "short"},
                    {
                        "role": "assistant",
                        "content": "very long message from assistant",
                    },
                ]
            }
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["truncated"] is True
    assert len(result["compressed_history"]) == 1
    assert "assistant" in result["summary"]


@pytest.mark.asyncio
async def test_conversation_compressor_adds_ellipsis_for_overflow() -> None:
    node = ConversationCompressorNode(
        name="compressor", max_tokens=3, preserve_recent=2
    )
    state = State(
        inputs={},
        results={
            "conversation_state": {
                "conversation_history": [
                    {"role": "user", "content": "one two"},
                    {"role": "assistant", "content": "three four"},
                ]
            }
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["summary"].endswith("...")


def test_memory_turn_requires_content() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        MemoryTurn(role="user", content="   ")


@pytest.mark.asyncio
async def test_memory_store_prune_and_expiry_paths() -> None:
    store = InMemoryMemoryStore()
    await store.append_turn("sess-x", MemoryTurn(role="user", content="hello"))

    assert len(await store.load_history("sess-x")) == 1  # limit=None branch
    await store.prune("missing", max_turns=1)  # history is None branch
    await store.prune("sess-x", max_turns=None)  # no-op branch

    await store.write_summary("sess-x", summary="keep", ttl_seconds=1)
    store.summaries["sess-x"] = ("keep", time.time() - 1)

    assert await store.get_summary("sess-x") is None
    assert "sess-x" not in store.summaries


@pytest.mark.asyncio
async def test_memory_store_retains_history_when_summary_expires() -> None:
    store = InMemoryMemoryStore()
    await store.append_turn("sess-retain", MemoryTurn(role="user", content="hello"))
    await store.write_summary("sess-retain", summary="temp", ttl_seconds=1)

    store.summaries["sess-retain"] = ("temp", time.time() - 1)

    assert await store.get_summary("sess-retain") is None
    assert len(await store.load_history("sess-retain")) == 1


@pytest.mark.asyncio
async def test_conversation_state_requires_session_id() -> None:
    node = ConversationStateNode(name="conversation_state")
    state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(ValueError, match="requires a non-empty session id"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_conversation_compressor_validates_history_payload() -> None:
    node = ConversationCompressorNode(name="compressor")
    state = State(
        inputs={}, results={"conversation_state": {}}, structured_response=None
    )

    with pytest.raises(
        ValueError, match="conversation_history must be provided as a list"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_conversation_compressor_requires_turns() -> None:
    node = ConversationCompressorNode(name="compressor")
    state = State(
        inputs={},
        results={"conversation_state": {"conversation_history": []}},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="requires at least one turn"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_topic_shift_detector_flags_divergence() -> None:
    node = TopicShiftDetectorNode(name="shift", similarity_threshold=0.4)
    state = State(
        inputs={"query": "Switch to pricing details"},
        results={
            "conversation_state": {
                "conversation_history": [
                    {"role": "user", "content": "Tell me about embedding quality"}
                ]
            }
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["is_shift"] is True
    assert result["route"] == "clarify"


@pytest.mark.asyncio
async def test_topic_shift_detector_handles_missing_query() -> None:
    node = TopicShiftDetectorNode(name="shift")
    state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(ValueError, match="requires a non-empty query"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_topic_shift_detector_handles_missing_history() -> None:
    node = TopicShiftDetectorNode(name="shift")
    state = State(
        inputs={"query": "hello"},
        results={"conversation_state": None},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["route"] == "continue"
    assert result["reason"] == "no_history"


@pytest.mark.asyncio
async def test_topic_shift_detector_validates_history_type() -> None:
    node = TopicShiftDetectorNode(name="shift")
    state = State(
        inputs={"query": "hi"},
        results={"conversation_state": "oops"},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="must be provided as a list"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_topic_shift_detector_handles_empty_tokens() -> None:
    node = TopicShiftDetectorNode(name="shift", similarity_threshold=0.1)
    state = State(
        inputs={"query": "and"},
        results={
            "conversation_state": {
                "conversation_history": [{"role": "user", "content": "the"}]
            }
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["similarity"] == 0.0
    assert result["is_shift"] is True


@pytest.mark.asyncio
async def test_query_clarification_generates_prompts() -> None:
    node = QueryClarificationNode(name="clarify")
    state = State(
        inputs={"query": "How does it work?"},
        results={
            "conversation_history": [
                {"role": "assistant", "content": "It handles retrieval and generation."}
            ]
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["needs_clarification"] is True
    assert any("specific" in question for question in result["clarifications"])


@pytest.mark.asyncio
async def test_query_clarification_handles_or_branch_and_summary_hint() -> None:
    node = QueryClarificationNode(name="clarify", max_questions=3)
    state = State(
        inputs={"query": "this or that"},
        results={"conversation_history": {"summary": "previous summary"}},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert "option" in " ".join(result["clarifications"])
    assert result["context_hint"] == "previous summary"


@pytest.mark.asyncio
async def test_query_clarification_requires_query() -> None:
    node = QueryClarificationNode(name="clarify")
    state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(ValueError, match="requires a non-empty query"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_memory_summarizer_persists_summary_with_ttl() -> None:
    store = InMemoryMemoryStore()
    node = MemorySummarizerNode(
        name="summarizer",
        memory_store=store,
        retention_seconds=10,
        max_summary_tokens=10,
    )
    state = State(
        inputs={"session_id": "sess-99"},
        results={
            "conversation_state": {
                "conversation_history": [
                    {"role": "user", "content": "We discussed retrieval latency"},
                    {"role": "assistant", "content": "Latency targets are strict."},
                ]
            }
        },
        structured_response=None,
    )

    result = await node.run(state, {})
    summary = await store.get_summary("sess-99")

    assert result["turns_summarized"] == 2
    assert summary is not None
    assert result["summary"] == summary
    assert result["ttl_seconds"] == 10


@pytest.mark.asyncio
async def test_memory_summarizer_validates_inputs_and_retention() -> None:
    store = InMemoryMemoryStore()
    node = MemorySummarizerNode(
        name="summarizer", memory_store=store, retention_seconds=5
    )

    state_missing_id = State(inputs={}, results={}, structured_response=None)
    with pytest.raises(ValueError, match="non-empty session id"):
        await node.run(state_missing_id, {})

    invalid_retention = MemorySummarizerNode(
        name="summarizer", memory_store=store, retention_seconds=0
    )
    state = State(
        inputs={"session_id": "sess-100"}, results={}, structured_response=None
    )
    with pytest.raises(ValueError, match="retention_seconds must be positive"):
        await invalid_retention.run(state, {})

    node_no_history = MemorySummarizerNode(
        name="summarizer", memory_store=store, retention_seconds=1
    )
    state = State(
        inputs={"session_id": "sess-200"},
        results={"conversation_state": []},
        structured_response=None,
    )
    result = await node_no_history.run(state, {})

    assert result["summary"] == "No conversation history yet."

    retention_none = MemorySummarizerNode(
        name="summarizer", memory_store=store, retention_seconds=None
    )
    state = State(
        inputs={"session_id": "sess-201"},
        results={
            "conversation_state": {
                "conversation_history": [{"role": "user", "content": "short"}]
            }
        },
        structured_response=None,
    )

    result_none = await retention_none.run(state, {})

    assert result_none["ttl_seconds"] is None


@pytest.mark.asyncio
async def test_memory_summarizer_truncates_long_history() -> None:
    store = InMemoryMemoryStore()
    node = MemorySummarizerNode(
        name="summarizer", memory_store=store, retention_seconds=2, max_summary_tokens=3
    )
    state = State(
        inputs={"session_id": "sess-ellipsis"},
        results={
            "conversation_state": {
                "conversation_history": [
                    {"role": "user", "content": "one two three four"},
                ]
            }
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["summary"].endswith("...")


@pytest.mark.asyncio
async def test_memory_summarizer_uses_existing_summary() -> None:
    store = InMemoryMemoryStore()
    node = MemorySummarizerNode(name="summarizer", memory_store=store)
    state = State(
        inputs={"session_id": "sess-summary"},
        results={
            "conversation_state": {
                "summary": "provided",
                "conversation_history": [{"role": "user", "content": "ignored"}],
            }
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["summary"] == "provided"
