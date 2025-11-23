import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.conversational_search.query_processing import (
    ContextCompressorNode,
    CoreferenceResolverNode,
    QueryClassifierNode,
    QueryRewriteNode,
)


@pytest.mark.asyncio
async def test_query_rewrite_includes_recent_history() -> None:
    node = QueryRewriteNode(name="rewrite", history_window=2)
    state = State(
        inputs={
            "query": "Where does it run?",
            "conversation_history": [
                "We discussed the Orcheo platform",
                {"content": "It runs on Kubernetes."},
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert (
        "context: We discussed the Orcheo platform It runs on Kubernetes."
        in result["rewritten_query"]
    )
    assert result["original_query"] == "Where does it run?"


@pytest.mark.asyncio
async def test_query_rewrite_validates_history_format() -> None:
    node = QueryRewriteNode(name="rewrite-invalid")
    state = State(
        inputs={"query": "Tell me more", "conversation_history": "not-a-list"},
        results={},
        structured_response=None,
    )

    with pytest.raises(
        ValueError, match="conversation_history must be a list when provided"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_coreference_resolver_replaces_pronouns() -> None:
    node = CoreferenceResolverNode(name="coref")
    state = State(
        inputs={
            "query": "How does it scale?",
            "conversation_history": ["The Orcheo platform"],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["resolved_query"] == "How does The Orcheo platform scale?"
    assert result["antecedent"] == "The Orcheo platform"


@pytest.mark.asyncio
async def test_query_classifier_routes_to_intents() -> None:
    node = QueryClassifierNode(name="classifier")
    search_state = State(
        inputs={"query": "Where do I find the docs?"},
        results={},
        structured_response=None,
    )
    clarification_state = State(
        inputs={"query": "Can you clarify the index format"},
        results={},
        structured_response=None,
    )
    finalize_state = State(
        inputs={"query": "Thanks for the help"},
        results={},
        structured_response=None,
    )

    search_intent = await node.run(search_state, {})
    clarification_intent = await node.run(clarification_state, {})
    finalize_intent = await node.run(finalize_state, {})

    assert search_intent["intent"] == "search"
    assert clarification_intent["intent"] == "clarification"
    assert finalize_intent["intent"] == "finalize"


@pytest.mark.asyncio
async def test_context_compressor_deduplicates_and_enforces_budget() -> None:
    vector_results = [
        SearchResult(
            id="chunk-1",
            score=0.9,
            text="Orcheo improves graph workflows",
            metadata={"source": "vector"},
            source="vector",
            sources=["vector"],
        ),
        SearchResult(
            id="chunk-2",
            score=0.7,
            text="Orcheo improves graph workflows",
            metadata={"source": "bm25"},
            source="bm25",
            sources=["bm25"],
        ),
    ]
    bm25_results = [
        SearchResult(
            id="chunk-3",
            score=0.6,
            text="Another passage about orchestration",
            metadata={},
            source="bm25",
            sources=["bm25"],
        ),
    ]
    state = State(
        inputs={},
        results={"retrieval_results": {"vector": vector_results, "bm25": bm25_results}},
        structured_response=None,
    )
    node = ContextCompressorNode(name="compressor", max_tokens=10)

    result = await node.run(state, {})

    compressed = result["compressed_results"]
    assert len(compressed) == 2
    assert sorted(compressed[0].sources) == ["bm25", "vector"]
    assert result["dropped_results"] == 1
