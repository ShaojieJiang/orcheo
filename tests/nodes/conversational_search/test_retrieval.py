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
    DenseSearchNode,
    HybridFusionNode,
    SparseSearchNode,
)
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_dense_search_node_returns_ranked_results() -> None:
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

    node = DenseSearchNode(
        name="dense",
        vector_store=store,
        top_k=2,
        filter_metadata={"source": "demo"},
    )
    state = State(
        inputs={"query": "orcheo improves graphs"}, results={}, structured_response=None
    )

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["vec-0", "vec-1"]
    assert all("dense" in item.sources for item in result["results"])


@pytest.mark.asyncio
async def test_dense_search_node_requires_non_empty_query() -> None:
    node = DenseSearchNode(name="dense-empty", vector_store=InMemoryVectorStore())
    state = State(inputs={"query": ""}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="DenseSearchNode requires a non-empty query string"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_dense_search_node_async_embedder_returns_nested_list() -> None:
    async def embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 2.0]]

    node = DenseSearchNode(
        name="dense-async",
        vector_store=InMemoryVectorStore(),
        embedding_function=embed,
    )

    assert await node._embed(["test"]) == [[1.0, 2.0]]


@pytest.mark.asyncio
async def test_dense_search_node_embedder_validates_output_type() -> None:
    node = DenseSearchNode(
        name="dense-bad-embed",
        vector_store=InMemoryVectorStore(),
        embedding_function=lambda texts: [text for text in texts],
    )

    with pytest.raises(
        ValueError, match="Embedding function must return List\\[List\\[float\\]\\]"
    ):
        await node._embed(["test"])


@pytest.mark.asyncio
async def test_sparse_search_orders_chunks_by_score() -> None:
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
    node = SparseSearchNode(name="sparse", top_k=1)

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["chunk-1"]
    assert result["results"][0].metadata["page"] == 1


@pytest.mark.asyncio
async def test_sparse_search_requires_non_empty_query() -> None:
    node = SparseSearchNode(name="sparse")
    state = State(inputs={"query": "   "}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="SparseSearchNode requires a non-empty query string"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_sparse_search_requires_chunks() -> None:
    node = SparseSearchNode(name="sparse")
    state = State(inputs={"query": "bananas"}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="SparseSearchNode requires at least one chunk to search"
    ):
        await node.run(state, {})


def test_sparse_resolve_chunks_rejects_non_list_payload() -> None:
    node = SparseSearchNode(name="sparse")
    state = State(
        inputs={},
        results={"chunking_strategy": {"chunks": {"not": "a list"}}},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="chunks payload must be a list"):
        node._resolve_chunks(state)


def test_sparse_score_skips_zero_denominator() -> None:
    node = SparseSearchNode(name="sparse", b=1.0)
    document_tokens: list[str] = []
    query_tokens = ["missing"]
    corpus = [document_tokens, ["present"]]
    avg_length = (len(document_tokens) + len(corpus[1])) / len(corpus)

    assert node._bm25_score(document_tokens, query_tokens, corpus, avg_length) == 0.0


@pytest.mark.asyncio
async def test_hybrid_fusion_rrf_combines_sources() -> None:
    dense_results = [
        SearchResult(
            id="chunk-1",
            score=0.8,
            text="dense",
            metadata={},
            source="dense",
            sources=["dense"],
        ),
        SearchResult(
            id="chunk-2",
            score=0.7,
            text="dense2",
            metadata={},
            source="dense",
            sources=["dense"],
        ),
    ]
    sparse_results = [
        SearchResult(
            id="chunk-2",
            score=2.0,
            text="sparse",
            metadata={},
            source="sparse",
            sources=["sparse"],
        )
    ]
    state = State(
        inputs={},
        results={
            "retrieval_results": {"dense": dense_results, "sparse": sparse_results}
        },
        structured_response=None,
    )
    node = HybridFusionNode(name="hybrid", strategy="rrf", top_k=2)

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["chunk-2", "chunk-1"]
    assert set(result["results"][0].sources) == {"dense", "sparse"}


@pytest.mark.asyncio
async def test_hybrid_fusion_weighted_sum_respects_weights() -> None:
    retrievers = {
        "dense": [
            SearchResult(id="r1", score=0.5, text="", metadata={}, source="dense")
        ],
        "sparse": [
            SearchResult(id="r1", score=2.0, text="", metadata={}, source="sparse")
        ],
    }
    state = State(
        inputs={}, results={"retrieval_results": retrievers}, structured_response=None
    )
    node = HybridFusionNode(
        name="hybrid-weighted",
        strategy="weighted_sum",
        weights={"dense": 0.5, "sparse": 2.0},
        top_k=1,
    )

    result = await node.run(state, {})

    assert result["results"][0].score == pytest.approx(4.25)
    assert set(result["results"][0].sources) == {"dense", "sparse"}


@pytest.mark.asyncio
async def test_hybrid_fusion_requires_results_mapping() -> None:
    node = HybridFusionNode(name="hybrid")
    state = State(
        inputs={}, results={"retrieval_results": {}}, structured_response=None
    )

    with pytest.raises(
        ValueError, match="HybridFusionNode requires a mapping of retriever results"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_hybrid_fusion_requires_valid_strategy() -> None:
    node = HybridFusionNode(name="hybrid", strategy="bad")
    state = State(
        inputs={},
        results={
            "retrieval_results": {
                "dense": [
                    SearchResult(
                        id="r1", score=1.0, text="", metadata={}, source="dense"
                    )
                ]
            }
        },
        structured_response=None,
    )

    with pytest.raises(
        ValueError, match="strategy must be either 'rrf' or 'weighted_sum'"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_hybrid_fusion_rejects_non_list_entries() -> None:
    node = HybridFusionNode(name="hybrid")
    state = State(
        inputs={},
        results={"retrieval_results": {"dense": {"results": "not a list"}}},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="Retriever results for dense must be a list"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_hybrid_fusion_handles_payload_with_results_key() -> None:
    retrievers = {
        "dense": {
            "results": [
                SearchResult(
                    id="r2", score=0.5, text="payload", metadata={}, source="dense"
                )
            ]
        }
    }
    state = State(
        inputs={}, results={"retrieval_results": retrievers}, structured_response=None
    )
    node = HybridFusionNode(name="hybrid", strategy="rrf", top_k=1)

    result = await node.run(state, {})

    assert result["results"][0].id == "r2"
