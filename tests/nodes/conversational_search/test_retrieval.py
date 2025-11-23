import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.models import DocumentChunk, VectorRecord
from orcheo.nodes.conversational_search.retrieval import (
    BM25SearchNode,
    HybridFusionNode,
    VectorSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


class _StateFactory:
    @staticmethod
    def base_state(inputs: dict | None = None, results: dict | None = None) -> State:
        return State(
            inputs=inputs or {}, results=results or {}, structured_response=None
        )


@pytest.mark.asyncio
async def test_vector_search_node_returns_sorted_matches() -> None:
    store = InMemoryVectorStore()
    await store.upsert(
        [
            VectorRecord(
                id="chunk-1",
                values=[1.0, 0.0],
                text="alpha beta",
                metadata={"document_id": "doc-1", "chunk_index": 0},
            ),
            VectorRecord(
                id="chunk-2",
                values=[0.5, 0.5],
                text="beta gamma",
                metadata={
                    "document_id": "doc-1",
                    "chunk_index": 1,
                    "category": "demo",
                },
            ),
        ]
    )

    node = VectorSearchNode(
        name="vector_search",
        vector_store=store,
        embedding_function=lambda texts: [[1.0, 0.0] for _ in texts],
        top_k=2,
        score_threshold=0.2,
    )
    state = _StateFactory.base_state(inputs={"query": "alpha"})

    result = await node.run(state, {})

    matches = result["matches"]
    assert [match.id for match in matches] == ["chunk-1", "chunk-2"]
    assert matches[0].score > matches[1].score


@pytest.mark.asyncio
async def test_bm25_search_node_scores_chunks() -> None:
    chunks = [
        DocumentChunk(
            id="chunk-a",
            document_id="doc-1",
            index=0,
            content="orcheo search retrieval",
            metadata={},
        ),
        DocumentChunk(
            id="chunk-b",
            document_id="doc-2",
            index=0,
            content="search pipelines are modular",
            metadata={},
        ),
    ]
    state = _StateFactory.base_state(
        inputs={"query": "search retrieval"},
        results={"chunking_strategy": {"chunks": chunks}},
    )
    node = BM25SearchNode(name="bm25_search", top_k=1)

    result = await node.run(state, {})

    matches = result["matches"]
    assert len(matches) == 1
    assert matches[0].id == "chunk-a"
    assert matches[0].source == "bm25"


@pytest.mark.asyncio
async def test_hybrid_fusion_rrf_combines_sources() -> None:
    vector_match = {"id": "shared", "score": 0.9, "text": "vec", "metadata": {}}
    bm25_match = {"id": "shared", "score": 1.5, "text": "bm", "metadata": {}}
    state = _StateFactory.base_state(
        results={
            "vector_search": {"matches": [vector_match]},
            "bm25_search": {"matches": [bm25_match]},
        }
    )
    node = HybridFusionNode(name="hybrid", strategy="rrf", rrf_k=10, top_k=1)

    result = await node.run(state, {})

    fused = result["fused_results"]
    assert fused[0].id == "shared"
    assert set(fused[0].sources) == {"vector_search", "bm25_search"}


@pytest.mark.asyncio
async def test_hybrid_fusion_weighted_sum_respects_weights() -> None:
    state = _StateFactory.base_state(
        results={
            "vector_search": {
                "matches": [{"id": "a", "score": 0.5, "text": "v", "metadata": {}}]
            },
            "bm25_search": {
                "matches": [{"id": "a", "score": 2.0, "text": "b", "metadata": {}}]
            },
        }
    )
    node = HybridFusionNode(
        name="hybrid",
        strategy="weighted_sum",
        weights={"vector_search": 3.0, "bm25_search": 0.5},
        top_k=1,
    )

    result = await node.run(state, {})

    fused = result["fused_results"]
    assert fused[0].id == "a"
    assert fused[0].score == pytest.approx(3.0 * 0.5 + 0.5 * 2.0)
