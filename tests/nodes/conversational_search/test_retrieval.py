import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.models import SearchResult, VectorRecord
from orcheo.nodes.conversational_search.retrieval import (
    BM25SearchNode,
    HybridFusionNode,
    VectorSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


async def _embed_first_dimension(texts: list[str]) -> list[list[float]]:
    return [[1.0, 0.0] for _ in texts]


@pytest.mark.asyncio
async def test_vector_search_node_returns_ranked_results() -> None:
    store = InMemoryVectorStore()
    await store.upsert(
        [
            VectorRecord(
                id="a", values=[1.0, 0.0], text="alpha", metadata={"tag": "first"}
            ),
            VectorRecord(
                id="b", values=[0.2, 0.8], text="bravo", metadata={"tag": "second"}
            ),
        ]
    )
    node = VectorSearchNode(
        name="vector_search",
        vector_store=store,
        embedding_function=_embed_first_dimension,
        top_k=2,
    )
    state = State(inputs={"query": "alpha"}, results={}, structured_response=None)

    result = await node.run(state, {})

    matches = result["results"]
    assert [match.id for match in matches] == ["a", "b"]
    assert matches[0].metadata["tag"] == "first"


@pytest.mark.asyncio
async def test_vector_search_node_applies_metadata_filters() -> None:
    store = InMemoryVectorStore()
    await store.upsert(
        [
            VectorRecord(
                id="a", values=[1.0, 0.0], text="alpha", metadata={"tag": "keep"}
            ),
            VectorRecord(
                id="b", values=[1.0, 0.0], text="bravo", metadata={"tag": "skip"}
            ),
        ]
    )
    node = VectorSearchNode(
        name="vector_search",
        vector_store=store,
        embedding_function=_embed_first_dimension,
        filter_metadata={"tag": "keep"},
    )
    state = State(inputs={"query": "alpha"}, results={}, structured_response=None)

    result = await node.run(state, {})

    assert [match.id for match in result["results"]] == ["a"]


@pytest.mark.asyncio
async def test_bm25_search_node_ranks_corpus() -> None:
    corpus = [
        {"id": "doc-1", "content": "apple banana apple"},
        {"id": "doc-2", "content": "apple"},
        {"id": "doc-3", "content": "banana orange"},
    ]
    node = BM25SearchNode(name="bm25_search", documents_field="documents", top_k=2)
    state = State(
        inputs={"query": "apple banana"},
        results={"documents": corpus},
        structured_response=None,
    )

    result = await node.run(state, {})

    matches = result["results"]
    assert matches[0].id == "doc-1"
    assert len(matches) == 2


@pytest.mark.asyncio
async def test_bm25_search_rejects_non_list_payload() -> None:
    node = BM25SearchNode(name="bm25_search", documents_field="documents")
    state = State(
        inputs={"query": "test"}, results={"documents": "bad"}, structured_response=None
    )

    with pytest.raises(ValueError, match="documents payload must be a list"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_hybrid_fusion_rrf_combines_sources() -> None:
    vector_results = [
        SearchResult(id="a", content="alpha", score=0.9, sources=["vector"]),
        SearchResult(id="b", content="bravo", score=0.8, sources=["vector"]),
    ]
    bm25_results = [
        SearchResult(id="b", content="bravo", score=1.5, sources=["bm25"]),
        SearchResult(id="c", content="charlie", score=1.0, sources=["bm25"]),
    ]
    node = HybridFusionNode(name="hybrid", top_k=3)
    state = State(
        inputs={},
        results={
            "vector_search": {"results": vector_results},
            "bm25_search": {"results": bm25_results},
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    fused = result["results"]
    assert fused[0].id in {"a", "b"}
    assert "bm25" in fused[0].sources or "vector" in fused[0].sources


@pytest.mark.asyncio
async def test_hybrid_fusion_weighted_sum_prefers_weighted_source() -> None:
    vector_results = [
        SearchResult(id="a", content="alpha", score=0.2, sources=["vector"])
    ]
    bm25_results = [SearchResult(id="a", content="alpha", score=1.0, sources=["bm25"])]
    node = HybridFusionNode(
        name="hybrid",
        strategy="weighted_sum",
        weights={"vector_search": 3.0, "bm25_search": 1.0},
    )
    state = State(
        inputs={},
        results={
            "vector_search": {"results": vector_results},
            "bm25_search": {"results": bm25_results},
        },
        structured_response=None,
    )

    result = await node.run(state, {})

    fused = result["results"]
    assert fused[0].id == "a"
    assert fused[0].score == pytest.approx(1.6)
