from unittest.mock import MagicMock, patch
import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.generation import (
    GroundedGeneratorNode,
    StreamingGeneratorNode,
    _truncate_snippet,
)
from orcheo.nodes.conversational_search.models import SearchResult


def _state_with_context(query: str) -> State:
    results = {
        "retriever": {
            "results": [
                SearchResult(
                    id="chunk-1",
                    score=0.9,
                    text="Orcheo ships modular nodes for RAG workflows.",
                    metadata={"page": 1},
                    source="vector",
                ),
                SearchResult(
                    id="chunk-2",
                    score=0.8,
                    text="Grounded answers include citations.",
                    metadata={"page": 2},
                    source="bm25",
                ),
            ]
        }
    }
    return State(inputs={"query": query}, results=results, structured_response=None)


@pytest.mark.asyncio
async def test_grounded_generator_appends_citations() -> None:
    node = GroundedGeneratorNode(name="generator")
    state = _state_with_context("What does Orcheo provide?")

    result = await node.run(state, {})

    assert result["citations"]
    assert "[1]" in result["reply"]
    assert result["tokens_used"] > 0


@pytest.mark.asyncio
async def test_grounded_generator_resolves_context_from_results_field() -> None:
    node = GroundedGeneratorNode(name="generator", context_result_key="hybrid")
    source_state = _state_with_context("How are citations handled?")
    retrieval_results = source_state["results"]["retriever"]["results"]
    state = State(
        inputs=source_state["inputs"],
        results={"results": retrieval_results, "hybrid": {}},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["citations"][0]["source_id"] == "chunk-1"


# Retry logic has been removed - retries should be configured via model_kwargs


@pytest.mark.asyncio
async def test_grounded_generator_requires_query_and_context() -> None:
    node = GroundedGeneratorNode(name="generator")
    empty_state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="GroundedGeneratorNode requires a non-empty query string"
    ):
        await node.run(empty_state, {})

    # Test non-RAG mode: works without context
    state = State(inputs={"query": "hi"}, results={}, structured_response=None)
    result = await node.run(state, {})
    assert result["mode"] == "non_rag"
    assert result["citations"] == []
    assert "reply" in result


@pytest.mark.asyncio
async def test_grounded_generator_rejects_non_list_context_payload() -> None:
    node = GroundedGeneratorNode(name="generator")
    state = State(
        inputs={"query": "hi"},
        results={"retriever": {"results": "not-a-list"}},
        structured_response=None,
    )

    with pytest.raises(
        ValueError, match="Context payload must be a list of retrieval results"
    ):
        await node.run(state, {})


def test_truncate_snippet_enforces_length_and_removes_newlines() -> None:
    text = "  first line\nsecond line third line extra \n"
    snippet = _truncate_snippet(text, limit=25)

    assert "second line" in snippet
    assert "\n" not in snippet
    assert snippet.endswith("…")
    assert len(snippet) <= 25


def test_truncate_snippet_returns_empty_when_limit_non_positive() -> None:
    assert _truncate_snippet("Should be ignored", limit=0) == ""


def test_truncate_snippet_returns_ellipsis_for_minimum_limit() -> None:
    assert _truncate_snippet("visible", limit=1) == "…"


def test_truncate_snippet_handles_truncated_whitespace() -> None:
    class FakeText:
        def strip(self) -> str:  # return whitespace even after strip
            return "    "

    assert _truncate_snippet(FakeText(), limit=3) == "…"


def test_attach_citations_returns_completion_when_no_markers() -> None:
    node = GroundedGeneratorNode(name="generator")

    assert node._attach_citations("answer", []) == "answer"


def test_attach_citations_handles_footnote_style() -> None:
    node = GroundedGeneratorNode(name="generator", citation_style="footnote")
    citations = [
        {
            "id": "1",
            "source_id": "chunk-1",
            "snippet": "text",
            "sources": [],
        }
    ]

    result = node._attach_citations("answer", citations)

    assert result == "answer\n\nFootnotes: [1]"


def test_attach_citations_handles_endnote_style() -> None:
    node = GroundedGeneratorNode(name="generator", citation_style="endnote")
    citations = [
        {
            "id": "1",
            "source_id": "chunk-1",
            "snippet": "text",
            "sources": [],
        }
    ]

    result = node._attach_citations("answer", citations)

    assert result == "answer\n\nEndnotes: [1]"


# Retry logic has been removed - retries should be configured via model_kwargs


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_result", [123, "   "])
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_invoke_ai_model_rejects_invalid_response(
    mock_create_agent, invalid_result
) -> None:
    # Mock the agent to return invalid result
    async def invalid_invoke(state):
        return {
            "messages": [
                MagicMock(content=invalid_result),
            ]
        }

    mock_agent = MagicMock()
    mock_agent.ainvoke = invalid_invoke
    mock_create_agent.return_value = mock_agent

    node = GroundedGeneratorNode(name="generator", ai_model="gpt-4")

    with pytest.raises(ValueError, match="Agent must return a non-empty string"):
        await node._invoke_ai_model("prompt")


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_grounded_generator_with_history_containing_empty_turns(
    mock_create_agent,
) -> None:
    """Test that history with non-dict items and empty content is handled."""

    async def mock_invoke(state):
        return {"messages": [MagicMock(content="Response with citations [1]")]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = GroundedGeneratorNode(name="generator", ai_model="gpt-4")
    state = _state_with_context("test query")
    # Mix of valid, invalid, and empty history items
    state["inputs"]["history"] = [
        {"role": "user", "content": "first"},
        "not a dict",  # Invalid item
        {"role": "user", "content": ""},  # Empty content
        {"role": "assistant", "content": ""},  # Empty content
        {"role": "other", "content": "ignored"},  # Wrong role
        {"role": "user", "content": "second"},
    ]

    result = await node.run(state, {})

    assert result["mode"] == "rag"
    assert len(result["citations"]) > 0


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_extract_response_text_from_dict_message(mock_create_agent) -> None:
    """Test extracting response text from dict message."""

    async def mock_invoke(state):
        return {"messages": [{"content": "Response text [1]"}]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = GroundedGeneratorNode(name="generator", ai_model="gpt-4")
    state = _state_with_context("test query")

    result = await node.run(state, {})

    assert "Response text" in result["reply"]


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_extract_response_text_from_non_message_object(mock_create_agent) -> None:
    """Test extracting response when message is not dict or has no content attr."""

    async def mock_invoke(state):
        # Return a message that's neither dict nor has content attribute
        return {"messages": ["plain string message"]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = GroundedGeneratorNode(name="generator", ai_model="gpt-4")
    state = _state_with_context("test query")

    result = await node.run(state, {})

    assert "plain string message" in result["reply"]


@pytest.mark.asyncio
async def test_grounded_generator_non_rag_mode() -> None:
    """Test non-RAG mode when no context is available."""
    node = GroundedGeneratorNode(name="generator")
    state = State(
        inputs={"query": "What is the weather?"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["mode"] == "non_rag"
    assert result["citations"] == []
    assert "reply" in result
    assert result["tokens_used"] > 0


@pytest.mark.asyncio
async def test_estimate_tokens_from_history_with_invalid_items() -> None:
    """Test token estimation with history containing invalid items."""
    node = GroundedGeneratorNode(name="generator")

    # History with non-dict items and empty content
    history = [
        {"role": "user", "content": "hello"},
        "not a dict",
        {"role": "user", "content": ""},
        {"role": "assistant"},  # Missing content
        {"role": "user", "content": "world"},
    ]

    tokens = node._estimate_tokens_from_history(history, "query", "response")

    # Should only count valid content: "hello", "world", "query", "response"
    assert tokens > 0


# StreamingGeneratorNode tests


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_streaming_generator_with_history_edge_cases(mock_create_agent) -> None:
    """Test StreamingGeneratorNode with history containing edge cases."""
    from orcheo.nodes.conversational_search.generation import StreamingGeneratorNode

    async def mock_invoke(state):
        return {"messages": [MagicMock(content="Streaming response")]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = StreamingGeneratorNode(name="streamer", ai_model="gpt-4")
    state = State(
        inputs={
            "message": "test query",
            "history": [
                {"role": "user", "content": "first"},
                "not a dict",  # Invalid
                {"role": "user", "content": ""},  # Empty
                {"role": "assistant", "content": ""},  # Empty
                {"role": "other", "content": "ignored"},  # Wrong role
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["reply"] == "Streaming response"


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_streaming_generator_extract_from_dict_message(mock_create_agent) -> None:
    """Test StreamingGeneratorNode extracting text from dict message."""
    from orcheo.nodes.conversational_search.generation import StreamingGeneratorNode

    async def mock_invoke(state):
        return {"messages": [{"content": "Dict response"}]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = StreamingGeneratorNode(name="streamer", ai_model="gpt-4")
    state = State(
        inputs={"message": "test"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["reply"] == "Dict response"


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_streaming_generator_extract_from_non_message_result(
    mock_create_agent,
) -> None:
    """Test StreamingGeneratorNode with non-dict result."""
    from orcheo.nodes.conversational_search.generation import StreamingGeneratorNode

    async def mock_invoke(state):
        # Return non-dict result
        return "plain result"

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = StreamingGeneratorNode(name="streamer", ai_model="gpt-4")
    state = State(
        inputs={"message": "test"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["reply"] == "plain result"


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_grounded_generator_with_valid_assistant_history(
    mock_create_agent,
) -> None:
    """Test that valid assistant history is correctly processed."""

    async def mock_invoke(state):
        return {"messages": [MagicMock(content="Response")]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = GroundedGeneratorNode(name="generator", ai_model="gpt-4")
    state = _state_with_context("query")
    state["inputs"]["history"] = [{"role": "assistant", "content": "previous answer"}]

    await node.run(state, {})
    # Implicitly covers line 192 by executing the path


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_grounded_generator_handles_direct_string_result(
    mock_create_agent,
) -> None:
    """Test handling of direct string result from agent."""

    async def mock_invoke(state):
        return "Direct string response"

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = GroundedGeneratorNode(name="generator", ai_model="gpt-4")
    state = _state_with_context("query")

    result = await node.run(state, {})
    assert "Direct string response" in result["reply"]


def test_estimate_tokens_static_method() -> None:
    """Test the static _estimate_tokens method."""
    # "hello" + "world" -> "helloworld" -> 1 token
    count = GroundedGeneratorNode._estimate_tokens("hello", "world")
    assert count == 1

    # "hello " + "world" -> "hello world" -> 2 tokens
    count = GroundedGeneratorNode._estimate_tokens("hello ", "world")
    assert count == 2


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_streaming_generator_with_valid_assistant_history(
    mock_create_agent,
) -> None:
    """Test StreamingGeneratorNode with valid assistant history."""

    async def mock_invoke(state):
        return {"messages": [MagicMock(content="Response")]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = StreamingGeneratorNode(name="streamer", ai_model="gpt-4")
    state = State(
        inputs={
            "message": "query",
            "history": [{"role": "assistant", "content": "previous"}],
        },
        results={},
        structured_response=None,
    )

    await node.run(state, {})
    # Implicitly covers line 375


@pytest.mark.asyncio
@patch("orcheo.nodes.conversational_search.generation.create_agent")
async def test_streaming_generator_handles_string_message_in_list(
    mock_create_agent,
) -> None:
    """Test StreamingGeneratorNode handling string message in messages list."""

    async def mock_invoke(state):
        return {"messages": ["string message"]}

    mock_agent = MagicMock()
    mock_agent.ainvoke = mock_invoke
    mock_create_agent.return_value = mock_agent

    node = StreamingGeneratorNode(name="streamer", ai_model="gpt-4")
    state = State(
        inputs={"message": "query"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})
    assert result["reply"] == "string message"
