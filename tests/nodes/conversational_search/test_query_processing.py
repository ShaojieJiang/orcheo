from __future__ import annotations

import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search import query_processing
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.conversational_search.query_processing import (
    ContextCompressorNode,
    CoreferenceResolverNode,
    QueryClassifierNode,
    QueryRewriteNode,
)


@pytest.mark.asyncio
async def test_query_rewrite_appends_context_when_pronoun_present() -> None:
    node = QueryRewriteNode(name="rewrite")
    state = State(
        inputs={
            "query": "How does it work?",
            "history": [
                {"role": "assistant", "content": "Apollo program landed on the moon"},
                {"role": "user", "content": "Tell me about Apollo"},
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert "Apollo program landed on the moon" in result["rewritten_query"]
    assert result["history_used"][0] == "Apollo program landed on the moon"


@pytest.mark.asyncio
async def test_coreference_resolver_replaces_pronoun_with_referent() -> None:
    node = CoreferenceResolverNode(name="coref")
    state = State(
        inputs={
            "query": "When did it launch?",
            "history": ["The Apollo program was NASA's moonshot initiative"],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["referent"] == "Apollo"
    assert "Apollo" in result["resolved_query"]


@pytest.mark.asyncio
async def test_query_classifier_detects_finalization_and_clarification() -> None:
    classifier = QueryClassifierNode(name="classifier")

    final_state = State(
        inputs={"query": "Thanks, that's all"}, results={}, structured_response=None
    )
    final_result = await classifier.run(final_state, {})

    clarify_state = State(
        inputs={"query": "Can you clarify the timeline?"},
        results={},
        structured_response=None,
    )
    clarify_result = await classifier.run(clarify_state, {})

    assert final_result["intent"] == "finalization"
    assert clarify_result["intent"] == "clarification"


def test_helpers_cover_normalization_and_empty_history() -> None:
    history = ["  Trim me  ", {"content": "Keep me"}, 99]
    assert query_processing._coerce_history_entries(history) == ["Trim me", "Keep me"]
    assert query_processing._derive_referent([]) is None
    assert query_processing._derive_referent(["   "]) is None
    assert query_processing._derive_referent(["The"]) is None


@pytest.mark.asyncio
async def test_context_compressor_deduplicates_and_respects_budget() -> None:
    compressor = ContextCompressorNode(name="compressor", max_tokens=4)
    results = [
        SearchResult(
            id="chunk-1",
            score=0.9,
            text="alpha beta gamma delta",
            metadata={},
            source="vector",
            sources=["vector"],
        ),
        SearchResult(
            id="chunk-2",
            score=0.5,
            text="alpha beta gamma delta",
            metadata={},
            source="bm25",
            sources=["bm25"],
        ),
    ]
    state = State(
        inputs={},
        results={"retrieval_results": {"results": results}},
        structured_response=None,
    )

    result = await compressor.run(state, {})

    assert len(result["results"]) == 1
    assert result["dropped"] == 1
    assert result["token_count"] == 4


@pytest.mark.asyncio
async def test_query_rewrite_appends_context_without_pronoun() -> None:
    node = QueryRewriteNode(name="rewrite-context")
    state = State(
        inputs={
            "query": "Explain the retrieval pipeline",
            "history": [
                "First note about hybrid search",
                123,
            ],
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["rewritten_query"].endswith("First note about hybrid search")
    assert len(result["history_used"]) == 1


@pytest.mark.asyncio
async def test_query_rewrite_requires_non_empty_query() -> None:
    node = QueryRewriteNode(name="rewrite-empty")
    state = State(inputs={"query": "   "}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="QueryRewriteNode requires a non-empty query string"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_query_rewrite_returns_original_without_history() -> None:
    node = QueryRewriteNode(name="rewrite-original")
    state = State(inputs={"query": "Stand-alone"}, results={}, structured_response=None)

    result = await node.run(state, {})

    assert result["rewritten_query"] == "Stand-alone"


@pytest.mark.asyncio
async def test_query_rewrite_validates_history_type() -> None:
    node = QueryRewriteNode(name="rewrite-history-type")
    state = State(
        inputs={"query": "Check", "history": "oops"},
        results={},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="history payload must be a list"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_coreference_resolver_validates_history_type_and_fallback() -> None:
    node = CoreferenceResolverNode(name="coref-invalid")
    state = State(
        inputs={"query": "What is it?", "history": "bad"},
        results={},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="history payload must be a list"):
        await node.run(state, {})

    with pytest.raises(
        ValueError, match="CoreferenceResolverNode requires a non-empty query string"
    ):
        await node.run(
            State(inputs={"query": "  "}, results={}, structured_response=None),
            {},
        )

    fallback_state = State(
        inputs={
            "query": "Where was it used?",
            "history": ["used in production systems"],
        },
        results={},
        structured_response=None,
    )

    fallback_result = await node.run(fallback_state, {})

    assert fallback_result["referent"] == "systems"
    assert "systems" in fallback_result["resolved_query"]


@pytest.mark.asyncio
async def test_coreference_resolver_handles_empty_history() -> None:
    node = CoreferenceResolverNode(name="coref-empty")
    state = State(
        inputs={"query": "What is it?", "history": []},
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["referent"] is None
    assert result["resolved_query"] == "What is it?"


@pytest.mark.asyncio
async def test_query_classifier_handles_search_intent_and_validation() -> None:
    classifier = QueryClassifierNode(name="classifier-search")

    state = State(
        inputs={"query": "What is Orcheo?"}, results={}, structured_response=None
    )
    result = await classifier.run(state, {})

    assert result["intent"] == "search"

    invalid_state = State(inputs={"query": ""}, results={}, structured_response=None)
    with pytest.raises(
        ValueError, match="QueryClassifierNode requires a non-empty query string"
    ):
        await classifier.run(invalid_state, {})

    neutral_state = State(
        inputs={"query": "Provide summary"}, results={}, structured_response=None
    )
    neutral_result = await classifier.run(neutral_state, {})

    assert neutral_result["intent"] == "search"


@pytest.mark.asyncio
async def test_context_compressor_validates_results_and_budget_breaks() -> None:
    compressor = ContextCompressorNode(name="compressor-empty", max_tokens=5)
    empty_state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="ContextCompressorNode requires at least one SearchResult"
    ):
        await compressor.run(empty_state, {})

    invalid_payload_state = State(
        inputs={},
        results={"retrieval_results": {"results": "invalid"}},
        structured_response=None,
    )

    with pytest.raises(
        ValueError, match="retrieval results must be provided as a list"
    ):
        await compressor.run(invalid_payload_state, {})

    rich_state = State(
        inputs={},
        results={
            "retrieval_results": {
                "results": [
                    SearchResult(
                        id="chunk-1",
                        score=0.9,
                        text="alpha beta gamma",
                        metadata={},
                        source="vector",
                        sources=["vector"],
                    ),
                    SearchResult(
                        id="chunk-2",
                        score=0.8,
                        text="delta epsilon zeta eta",
                        metadata={},
                        source="bm25",
                        sources=["bm25"],
                    ),
                ]
            }
        },
        structured_response=None,
    )

    budgeted = await compressor.run(rich_state, {})

    assert [item.id for item in budgeted["results"]] == ["chunk-1"]
    assert budgeted["dropped"] == 1


@pytest.mark.asyncio
async def test_context_compressor_handles_duplicates_without_deduplication() -> None:
    compressor = ContextCompressorNode(
        name="compressor-no-dedup", deduplicate=False, max_tokens=6
    )
    state = State(
        inputs={},
        results={
            "retrieval_results": {
                "results": [
                    SearchResult(
                        id="chunk-1",
                        score=0.9,
                        text="alpha beta",
                        metadata={},
                        source="vector",
                        sources=["vector"],
                    ),
                    SearchResult(
                        id="chunk-2",
                        score=0.8,
                        text="gamma delta epsilon",
                        metadata={},
                        source="bm25",
                        sources=["bm25"],
                    ),
                ]
            }
        },
        structured_response=None,
    )

    result = await compressor.run(state, {})

    assert [item.id for item in result["results"]] == ["chunk-1", "chunk-2"]
