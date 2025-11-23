import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.conversational_search.query_processing import (
    ContextCompressorNode,
    CoreferenceResolverNode,
    QueryClassifierNode,
    QueryRewriteNode,
    _normalize_messages,
)


@pytest.mark.asyncio
async def test_query_rewrite_appends_context_for_pronoun() -> None:
    node = QueryRewriteNode(name="rewrite", max_history_messages=2)
    state = State(
        inputs={
            "query": "How does it scale?",
            "history": [
                {"role": "user", "content": "Tell me about the vector store"},
                {"role": "assistant", "content": "It supports namespaces"},
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["used_history"] is True
    assert "Context: Tell me about the vector store" in result["query"]


@pytest.mark.asyncio
async def test_coreference_resolution_replaces_first_pronoun() -> None:
    node = CoreferenceResolverNode(name="coref")
    state = State(
        inputs={
            "query": "How does it work?",
            "history": [{"role": "user", "content": "The retriever pipeline"}],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["resolved"] is True
    assert result["antecedent"] == "The retriever pipeline"
    assert "The retriever pipeline" in result["query"]


@pytest.mark.asyncio
async def test_query_classifier_uses_heuristics() -> None:
    node = QueryClassifierNode(name="classifier")
    state = State(
        inputs={"query": "Can you clarify which one to use?"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["classification"] == "clarification"
    assert result["confidence"] == pytest.approx(0.8)


@pytest.mark.asyncio
async def test_query_classifier_defaults_to_search() -> None:
    node = QueryClassifierNode(name="classifier-default")
    state = State(
        inputs={"query": "List retrieval options"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result == {"classification": "search", "confidence": 0.6}


@pytest.mark.asyncio
async def test_query_classifier_finalization_branch() -> None:
    node = QueryClassifierNode(name="classifier-finalize")
    state = State(
        inputs={"query": "Thanks for the help!"},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result == {"classification": "finalization", "confidence": 0.9}


@pytest.mark.asyncio
async def test_context_compressor_deduplicates_and_budgets() -> None:
    node = ContextCompressorNode(name="compress", max_tokens=4)
    results = [
        SearchResult(id="a", score=0.9, text="first chunk", metadata={}),
        SearchResult(id="a", score=0.8, text="duplicate chunk", metadata={}),
        SearchResult(id="b", score=0.5, text="second chunk here", metadata={}),
    ]
    state = State(
        inputs={},
        results={"retrieval_results": results},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["a"]
    assert result["total_tokens"] == 2
    assert result["truncated"] is True


def test_normalize_messages_handles_mixed_payloads() -> None:
    history = ["hello", {"content": "world"}, {"missing": "content"}, 42]

    assert _normalize_messages(history) == ["hello", "world"]


@pytest.mark.asyncio
async def test_query_rewrite_handles_non_pronoun_query() -> None:
    node = QueryRewriteNode(name="rewrite-no-context")
    state = State(
        inputs={"query": "Tell me about graphs", "history": ["previous turn"]},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["query"] == "Tell me about graphs"
    assert result["used_history"] is False


@pytest.mark.asyncio
async def test_query_rewrite_validates_history_type() -> None:
    node = QueryRewriteNode(name="rewrite-error")
    state = State(
        inputs={"query": "hello", "history": "not-a-list"},
        results={},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="history must be a list of messages"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_query_rewrite_requires_query() -> None:
    node = QueryRewriteNode(name="rewrite-empty")
    state = State(inputs={"query": "   "}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="QueryRewriteNode requires a non-empty query string"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_coreference_resolver_handles_missing_referent() -> None:
    node = CoreferenceResolverNode(name="coref-none")
    state = State(
        inputs={"query": "Where is it?", "history": []},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result == {"query": "Where is it?", "resolved": False, "antecedent": None}


@pytest.mark.asyncio
async def test_coreference_resolver_without_matching_pronoun() -> None:
    node = CoreferenceResolverNode(name="coref-no-pronoun")
    state = State(
        inputs={
            "query": "Explain the architecture",
            "history": ["Vector store overview"],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result == {
        "query": "Explain the architecture",
        "resolved": False,
        "antecedent": None,
    }


@pytest.mark.asyncio
async def test_coreference_resolver_validates_history_type() -> None:
    node = CoreferenceResolverNode(name="coref-error")
    state = State(
        inputs={"query": "hello", "history": "oops"},
        results={},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="history must be a list of messages"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_coreference_resolver_requires_query() -> None:
    node = CoreferenceResolverNode(name="coref-empty")
    state = State(inputs={"query": ""}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="CoreferenceResolverNode requires a non-empty query string"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_query_classifier_requires_query() -> None:
    node = QueryClassifierNode(name="classifier-empty")
    state = State(inputs={"query": ""}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="QueryClassifierNode requires a non-empty query string"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_context_compressor_handles_results_mapping() -> None:
    node = ContextCompressorNode(name="compress-mapping", max_tokens=10)
    search_result = SearchResult(id="a", score=0.5, text="small chunk", metadata={})
    state = State(
        inputs={},
        results={"retrieval_results": {"results": [search_result]}},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["results"][0].id == "a"
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_context_compressor_requires_results() -> None:
    node = ContextCompressorNode(name="compress-missing")
    state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="ContextCompressorNode requires retrieval results to compress"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_context_compressor_validates_entries_type() -> None:
    node = ContextCompressorNode(name="compress-type")
    state = State(
        inputs={}, results={"retrieval_results": "not-a-list"}, structured_response=None
    )

    with pytest.raises(
        ValueError, match="retrieval results must be provided as a list"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_context_compressor_without_deduplication() -> None:
    node = ContextCompressorNode(
        name="compress-no-dedup", max_tokens=10, deduplicate=False
    )
    results = [
        SearchResult(id="a", score=0.2, text="alpha beta", metadata={}),
        SearchResult(id="a", score=0.1, text="gamma delta", metadata={}),
    ]
    state = State(
        inputs={}, results={"retrieval_results": results}, structured_response=None
    )

    result = await node.run(state, {})

    assert [item.text for item in result["results"]] == ["alpha beta", "gamma delta"]
    assert result["truncated"] is False
