"""Tests for conversational search retrieval nodes."""

from typing import Any

import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.models import SearchResult, VectorRecord
from orcheo.nodes.conversational_search.retrieval import (
    BM25SearchNode,
    HybridFusionNode,
    VectorSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import (
    InMemoryVectorStore,
    PineconeVectorStore,
)


@pytest.mark.asyncio
async def test_vector_search_filters_and_excludes_metadata() -> None:
    store = InMemoryVectorStore(
        records={
            "keep": VectorRecord(
                id="keep",
                values=[1.0],
                text="matching text",
                metadata={"tag": "yes"},
            ),
            "drop": VectorRecord(
                id="drop",
                values=[1.0],
                text="other text",
                metadata={"tag": "no"},
            ),
        }
    )
    node = VectorSearchNode(
        name="vector_search",
        vector_store=store,
        filter_metadata={"tag": "yes"},
        include_metadata=False,
        embedding_function=lambda texts: [[1.0]],
    )
    state = State(inputs={"query": "hello"}, results={}, structured_response=None)

    result = await node.run(state, {})

    hits = result["results"]
    assert len(hits) == 1
    assert hits[0].id == "keep"
    assert hits[0].metadata == {}
    assert hits[0].source == "vector"
    assert hits[0].sources == ["vector"]


@pytest.mark.asyncio
async def test_bm25_search_ranks_and_truncates_results() -> None:
    node = BM25SearchNode(
        name="bm25",
        documents=[
            {"id": "doc-1", "content": "alpha beta beta", "metadata": {"m": 1}},
            {"id": "doc-2", "content": "gamma", "metadata": {"m": 2}},
        ],
        top_k=1,
        include_metadata=False,
    )
    state = State(inputs={"query": "beta"}, results={}, structured_response=None)

    result = await node.run(state, {})

    hits = result["results"]
    assert len(hits) == 1
    assert hits[0].id == "doc-1"
    assert hits[0].metadata == {}
    assert hits[0].source == "bm25"


@pytest.mark.asyncio
async def test_hybrid_fusion_rrf_prefers_combined_hits() -> None:
    state = State(
        inputs={},
        results={
            "vector_search": {
                "results": [
                    SearchResult(
                        id="a", content="A", score=0.9, metadata={}, sources=["vector"]
                    ),
                    SearchResult(
                        id="b", content="B", score=0.8, metadata={}, sources=["vector"]
                    ),
                ]
            },
            "bm25_search": {
                "results": [
                    SearchResult(
                        id="b", content="B", score=2.0, metadata={}, sources=["bm25"]
                    ),
                    SearchResult(
                        id="c", content="C", score=1.0, metadata={}, sources=["bm25"]
                    ),
                ]
            },
        },
        structured_response=None,
    )
    node = HybridFusionNode(name="fusion", strategy="rrf", top_k=2)

    result = await node.run(state, {})

    hits = result["results"]
    assert [hit.id for hit in hits] == ["b", "a"]
    assert hits[0].sources == ["vector", "bm25"]


@pytest.mark.asyncio
async def test_hybrid_fusion_weighted_sum_uses_weights() -> None:
    state = State(
        inputs={},
        results={
            "retrieval_results": {
                "vector": [
                    {"id": "x", "content": "X", "score": 0.6, "metadata": {}},
                ],
                "bm25": [
                    {"id": "y", "content": "Y", "score": 1.0, "metadata": {}},
                ],
            }
        },
        structured_response=None,
    )
    node = HybridFusionNode(
        name="fusion-weighted",
        retrieval_results_key="retrieval_results",
        strategy="weighted_sum",
        weights={"vector": 2.0, "bm25": 0.5},
    )

    result = await node.run(state, {})

    hits = result["results"]
    assert [hit.id for hit in hits][:1] == ["x"]
    assert hits[0].source == "vector"


@pytest.mark.asyncio
async def test_pinecone_search_preserves_text_without_metadata() -> None:
    class FakeIndex:
        def __init__(self) -> None:
            self.last_kwargs: dict[str, Any] | None = None

        def query(self, **kwargs: Any) -> dict[str, Any]:
            self.last_kwargs = kwargs
            return {
                "matches": [
                    {
                        "id": "doc-1",
                        "score": 0.42,
                        "metadata": {"text": "stored text", "keep": True},
                    }
                ]
            }

    class FakeClient:
        def __init__(self, index: FakeIndex) -> None:
            self.index = index

        def Index(self, _: str) -> FakeIndex:  # pragma: no cover - simple helper
            return self.index

    index = FakeIndex()
    store = PineconeVectorStore(index_name="demo", client=FakeClient(index))

    results = await store.search(
        query_vector=[0.1, 0.2], top_k=1, include_metadata=False
    )

    assert index.last_kwargs is not None
    assert index.last_kwargs["include_metadata"] is True

    assert len(results) == 1
    hit = results[0]
    assert hit.content == "stored text"
    assert hit.metadata == {}
