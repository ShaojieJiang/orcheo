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
    node = QueryRewriteNode(name="query_rewrite", max_history_turns=2)
    state = State(
        inputs={
            "query": "How does it scale?",
            "history": [
                {"role": "user", "content": "Tell me about vector stores"},
                {"role": "assistant", "content": "They index embeddings."},
                {"role": "user", "content": "What about BM25?"},
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert "BM25" in result["rewritten_query"]
    assert result["original_query"] == "How does it scale?"
    assert result["context_window"] == [
        {"role": "assistant", "content": "They index embeddings."},
        {"role": "user", "content": "What about BM25?"},
    ]


@pytest.mark.asyncio
async def test_coreference_resolver_prefers_entities_over_history() -> None:
    node = CoreferenceResolverNode(name="coref")
    state = State(
        inputs={
            "query": "How do we scale it?",
            "entities": ["the vector index"],
            "history": ["Discussed Pinecone tradeoffs"],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["antecedent"] == "the vector index"
    assert result["resolved_query"] == "How do we scale the vector index?"


@pytest.mark.asyncio
async def test_query_classifier_routes_intents() -> None:
    node = QueryClassifierNode(name="classifier")
    state_search = State(
        inputs={"query": "Find docs about RAG"}, results={}, structured_response=None
    )
    state_clarify = State(
        inputs={"query": "Which one?"}, results={}, structured_response=None
    )
    state_finalize = State(
        inputs={"query": "Thanks, that's all"}, results={}, structured_response=None
    )

    assert (await node.run(state_search, {}))["intent"] == "search"
    assert (await node.run(state_clarify, {}))["intent"] == "clarification"
    assert (await node.run(state_finalize, {}))["intent"] == "finalization"


@pytest.mark.asyncio
async def test_context_compressor_deduplicates_and_applies_budget() -> None:
    node = ContextCompressorNode(name="compressor", token_budget=6)
    payload = {
        "results": [
            SearchResult(id="1", score=1.0, text="alpha beta gamma", metadata={}),
            SearchResult(id="2", score=0.9, text="alpha   beta    gamma", metadata={}),
            SearchResult(id="3", score=0.8, text="delta epsilon", metadata={}),
        ]
    }
    state = State(
        inputs={}, results={"retrieval_results": payload}, structured_response=None
    )

    result = await node.run(state, {})

    kept_ids = [entry.id for entry in result["results"]]
    assert kept_ids == ["1", "3"]
    assert result["dropped_ids"] == ["2"]
    assert result["total_tokens"] == 5
