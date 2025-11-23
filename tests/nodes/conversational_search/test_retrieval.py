import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.ingestion import (
    deterministic_embedding_function,
)
from orcheo.nodes.conversational_search.models import (
    DocumentChunk,
    SearchResult,
    VectorRecord,
)
from orcheo.nodes.conversational_search.retrieval import (
    BM25SearchNode,
    HybridFusionNode,
    VectorSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_vector_search_node_returns_ranked_results() -> None:
    store = InMemoryVectorStore()
    texts = ["orcheo improves graphs", "another passage"]
    embeddings = deterministic_embedding_function(texts)
    await store.upsert(
        [
            VectorRecord(
                id=f"vec-{index}",
                values=embedding,
                text=text,
                metadata={"source": "demo", "index": index},
            )
            for index, (embedding, text) in enumerate(
                zip(embeddings, texts, strict=True)
            )
        ]
    )

    node = VectorSearchNode(
        name="vector",
        vector_store=store,
        top_k=2,
        filter_metadata={"source": "demo"},
    )
    state = State(
        inputs={"query": "orcheo improves graphs"}, results={}, structured_response=None
    )

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["vec-0", "vec-1"]
    assert all("vector" in item.sources for item in result["results"])


@pytest.mark.asyncio
async def test_bm25_search_orders_chunks_by_score() -> None:
    chunks = [
        DocumentChunk(
            id="chunk-1",
            document_id="doc-1",
            index=0,
            content="bananas bananas apples",
            metadata={"page": 1},
        ),
        DocumentChunk(
            id="chunk-2",
            document_id="doc-2",
            index=0,
            content="apples only",
            metadata={"page": 2},
        ),
    ]
    state = State(
        inputs={"query": "bananas"},
        results={"chunking_strategy": {"chunks": chunks}},
        structured_response=None,
    )
    node = BM25SearchNode(name="bm25", top_k=1)

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["chunk-1"]
    assert result["results"][0].metadata["page"] == 1


@pytest.mark.asyncio
async def test_hybrid_fusion_rrf_combines_sources() -> None:
    vector_results = [
        SearchResult(
            id="chunk-1",
            score=0.8,
            text="vector",
            metadata={},
            source="vector",
            sources=["vector"],
        ),
        SearchResult(
            id="chunk-2",
            score=0.7,
            text="vector2",
            metadata={},
            source="vector",
            sources=["vector"],
        ),
    ]
    bm25_results = [
        SearchResult(
            id="chunk-2",
            score=2.0,
            text="bm25",
            metadata={},
            source="bm25",
            sources=["bm25"],
        )
    ]
    state = State(
        inputs={},
        results={"retrieval_results": {"vector": vector_results, "bm25": bm25_results}},
        structured_response=None,
    )
    node = HybridFusionNode(name="hybrid", strategy="rrf", top_k=2)

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["chunk-2", "chunk-1"]
    assert set(result["results"][0].sources) == {"vector", "bm25"}


@pytest.mark.asyncio
async def test_hybrid_fusion_weighted_sum_respects_weights() -> None:
    retrievers = {
        "vector": [
            SearchResult(id="r1", score=0.5, text="", metadata={}, source="vector")
        ],
        "bm25": [SearchResult(id="r1", score=2.0, text="", metadata={}, source="bm25")],
    }
    state = State(
        inputs={}, results={"retrieval_results": retrievers}, structured_response=None
    )
    node = HybridFusionNode(
        name="hybrid-weighted",
        strategy="weighted_sum",
        weights={"vector": 0.5, "bm25": 2.0},
        top_k=1,
    )

    result = await node.run(state, {})

    assert result["results"][0].score == pytest.approx(4.25)
    assert set(result["results"][0].sources) == {"vector", "bm25"}
