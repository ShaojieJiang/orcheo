from types import SimpleNamespace
from typing import Any
import pytest
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.ingestion import (
    EmbeddingVector,
    register_embedding_method,
    resolve_embedding_method,
)
from orcheo.nodes.conversational_search.models import (
    DocumentChunk,
    SearchResult,
    VectorRecord,
)
from orcheo.nodes.conversational_search.retrieval import (
    DenseSearchNode,
    HybridFusionNode,
    PineconeRerankNode,
    SparseSearchNode,
    _resolve_retrieval_results,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
)


DEFAULT_TEST_RETRIEVAL_EMBEDDING = "test-retrieval-embedding"


def _test_retrieval_embedder(texts: list[str]) -> list[list[float]]:
    return [[float(len(text))] for text in texts]


register_embedding_method(DEFAULT_TEST_RETRIEVAL_EMBEDDING, _test_retrieval_embedder)


@pytest.mark.asyncio
async def test_dense_search_node_returns_ranked_results() -> None:
    store = InMemoryVectorStore()
    texts = ["orcheo improves graphs", "another passage"]
    embedder = resolve_embedding_method(DEFAULT_TEST_RETRIEVAL_EMBEDDING)
    embeddings = embedder(texts)
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
        embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING,
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
    node = DenseSearchNode(
        name="dense-empty",
        vector_store=InMemoryVectorStore(),
        embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING,
    )
    state = State(inputs={"query": ""}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="DenseSearchNode requires a non-empty query string"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_dense_search_node_async_embedder_returns_nested_list() -> None:
    async def embed(texts: list[str]) -> list[list[float]]:
        return [[1.0, 2.0]]

    register_embedding_method("dense-async", embed)
    node = DenseSearchNode(
        name="dense-async",
        vector_store=InMemoryVectorStore(),
        embedding_method="dense-async",
    )

    assert await node._embed(["test"]) == [[1.0, 2.0]]


@pytest.mark.asyncio
async def test_dense_search_node_embedder_validates_output_type() -> None:
    register_embedding_method("dense-bad", lambda texts: [text for text in texts])
    node = DenseSearchNode(
        name="dense-bad-embed",
        vector_store=InMemoryVectorStore(),
        embedding_method="dense-bad",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Embedding function must return List\\[List\\[float\\]\\] or "
            "sparse embedding payloads"
        ),
    ):
        await node._embed(["test"])


@pytest.mark.asyncio
async def test_dense_search_node_requires_dense_values() -> None:
    register_embedding_method(
        "dense-sparse-only",
        lambda texts: [{"sparse_values": {"indices": [1], "values": [0.5]}}],
    )
    node = DenseSearchNode(
        name="dense-sparse-only",
        vector_store=InMemoryVectorStore(),
        embedding_method="dense-sparse-only",
    )

    with pytest.raises(
        ValueError, match="Dense embeddings must include dense vector values"
    ):
        await node._embed(["query"])


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
    node = SparseSearchNode(
        name="sparse",
        top_k=1,
        embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING,
    )

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["chunk-1"]
    assert result["results"][0].metadata["page"] == 1


@pytest.mark.asyncio
async def test_sparse_search_requires_non_empty_query() -> None:
    node = SparseSearchNode(
        name="sparse", embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING
    )
    state = State(inputs={"query": "   "}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="SparseSearchNode requires a non-empty query string"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_sparse_search_requires_chunks() -> None:
    node = SparseSearchNode(
        name="sparse", embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING
    )
    state = State(inputs={"query": "bananas"}, results={}, structured_response=None)

    result = await node.run(state, {})

    assert result["results"] == []
    assert "warning" in result
    assert "SparseSearchNode did not receive any document chunks" in result["warning"]


@pytest.mark.asyncio
async def test_sparse_search_vector_store_candidates() -> None:
    store = InMemoryVectorStore()
    await store.upsert(
        [
            VectorRecord(
                id="chunk-1",
                values=[1.0, 0.0],
                text="apples apples bananas",
                metadata={"document_id": "doc-1", "chunk_index": 0},
            ),
            VectorRecord(
                id="chunk-2",
                values=[0.0, 1.0],
                text="apples oranges",
                metadata={"document_id": "doc-2", "chunk_index": 0},
            ),
        ]
    )

    register_embedding_method("sparse-vector-store", lambda texts: [[1.0, 0.0]])
    node = SparseSearchNode(
        name="sparse-vector-store",
        vector_store=store,
        vector_store_candidate_k=2,
        top_k=1,
        embedding_method="sparse-vector-store",
    )
    state = State(inputs={"query": "apples"}, results={}, structured_response=None)

    result = await node.run(state, {})

    assert [item.id for item in result["results"]] == ["chunk-1"]


@pytest.mark.asyncio
async def test_sparse_fetch_chunks_returns_empty_without_vector_store() -> None:
    node = SparseSearchNode(
        name="sparse-fetch-empty",
        embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING,
    )

    assert await node._fetch_chunks_from_vector_store("query") == []


@pytest.mark.asyncio
async def test_sparse_fetch_chunks_handles_vector_store_metadata() -> None:
    class StubStore(BaseVectorStore):
        matches: list[SearchResult] = Field(default_factory=list)

        async def upsert(self, records) -> None:
            del records

        async def search(
            self,
            query: list[float],
            top_k: int,
            filter_metadata: dict[str, Any] | None = None,
        ) -> list[SearchResult]:
            del query, top_k, filter_metadata
            return self.matches

    matches = [
        SearchResult(
            id="skip-text",
            score=0.0,
            text="",
            metadata={},
            source="stub",
            sources=["stub"],
        ),
        SearchResult(
            id="string-index",
            score=1.0,
            text="chunk text",
            metadata={"chunk_index": "not-int", "document_id": "doc-str"},
            source="stub",
            sources=["stub"],
        ),
        SearchResult(
            id="list-index",
            score=0.5,
            text="chunk two",
            metadata={"chunk_index": ["bad"], "document_id": 123},
            source="stub",
            sources=["stub"],
        ),
    ]
    store = StubStore(matches=matches)
    node = SparseSearchNode(
        name="sparse-fetch-metadata",
        vector_store=store,
        embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING,
    )

    chunks = await node._fetch_chunks_from_vector_store("query")

    assert [chunk.id for chunk in chunks] == ["string-index", "list-index"]
    assert chunks[0].index == 0
    assert chunks[1].document_id == "123"


@pytest.mark.asyncio
async def test_sparse_embed_async_embedder_returns_vectors() -> None:
    async def embed(texts: list[str]) -> list[list[float]]:
        return [[0.5] for _ in texts]

    register_embedding_method("sparse-async", embed)
    node = SparseSearchNode(
        name="sparse-async",
        embedding_method="sparse-async",
    )

    vectors = await node._embed(["test"])
    assert len(vectors) == 1
    vector = vectors[0]
    assert isinstance(vector, EmbeddingVector)
    assert vector.values == [0.5]
    assert vector.sparse_values is None


@pytest.mark.asyncio
async def test_sparse_embed_raises_on_invalid_payload() -> None:
    register_embedding_method("sparse-invalid", lambda texts: "bad")
    node = SparseSearchNode(
        name="sparse-invalid",
        embedding_method="sparse-invalid",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Embedding function must return List\\[List\\[float\\]\\] or "
            "sparse embedding payloads"
        ),
    ):
        await node._embed(["test"])


@pytest.mark.asyncio
async def test_sparse_embed_requires_dense_values() -> None:
    register_embedding_method(
        "sparse-sparse-only",
        lambda texts: [{"sparse_values": {"indices": [0], "values": [0.5]}}],
    )
    node = SparseSearchNode(
        name="sparse-sparse-only",
        embedding_method="sparse-sparse-only",
    )

    vectors = await node._embed(["query"])
    assert len(vectors) == 1
    vector = vectors[0]
    assert vector.values == []
    assert vector.sparse_values is not None
    assert vector.sparse_values.indices == [0]
    assert vector.sparse_values.values == [0.5]


def test_sparse_resolve_chunks_rejects_non_list_payload() -> None:
    node = SparseSearchNode(
        name="sparse", embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING
    )
    state = State(
        inputs={},
        results={"chunking_strategy": {"chunks": {"not": "a list"}}},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="chunks payload must be a list"):
        node._resolve_chunks(state)


def test_sparse_score_skips_zero_denominator() -> None:
    node = SparseSearchNode(
        name="sparse",
        b=1.0,
        embedding_method=DEFAULT_TEST_RETRIEVAL_EMBEDDING,
    )
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


@pytest.mark.asyncio
async def test_pinecone_rerank_returns_empty_for_missing_entries() -> None:
    node = PineconeRerankNode(name="pinecone")
    state = State(
        inputs={"query": "test"},
        results={"fusion": []},
        structured_response=None,
    )

    assert await node.run(state, {}) == {"results": []}


@pytest.mark.asyncio
async def test_pinecone_rerank_requires_inference_interface() -> None:
    entry = SearchResult(
        id="doc-1",
        score=1.0,
        text="passage",
        metadata={},
        source="fusion",
        sources=["fusion"],
    )
    node = PineconeRerankNode(name="pinecone")
    node.client = SimpleNamespace()
    state = State(
        inputs={"query": "what"}, results={"fusion": [entry]}, structured_response=None
    )

    with pytest.raises(
        RuntimeError,
        match="Pinecone client lacks an inference interface for reranking",
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_pinecone_rerank_handles_async_inference() -> None:
    entry = SearchResult(
        id="doc-1",
        score=1.0,
        text="passage",
        metadata={"topic": "test"},
        source="fusion",
        sources=["fusion"],
    )

    class StubInference:
        async def rerank(self, **__: Any) -> dict[str, Any]:
            return {
                "data": [
                    {
                        "document": {"_id": "doc-1", "chunk_text": "reranked"},
                        "score": 2.0,
                    }
                ]
            }

    node = PineconeRerankNode(
        name="pinecone", client=SimpleNamespace(inference=StubInference())
    )
    state = State(
        inputs={"query": "what"},
        results={"fusion": [entry]},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["results"][0].text == "reranked"
    assert result["results"][0].metadata == entry.metadata


def test_pinecone_rerank_requires_query_string() -> None:
    node = PineconeRerankNode(name="pinecone")

    with pytest.raises(
        ValueError,
        match="PineconeRerankNode requires a non-empty query string",
    ):
        node._resolve_query(
            State(inputs={"query": "   "}, results={}, structured_response=None)
        )


def test_pinecone_rerank_build_documents_includes_metadata() -> None:
    entry = SearchResult(
        id="doc-2",
        score=1.0,
        text="passage",
        metadata={"source": "rerank"},
        source="rerank",
        sources=["rerank"],
    )
    node = PineconeRerankNode(name="pinecone")

    documents = node._build_documents([entry])

    assert documents[0]["metadata"] == entry.metadata


def test_pinecone_rerank_uses_provided_client() -> None:
    stub = SimpleNamespace()
    node = PineconeRerankNode(name="pinecone")
    node.client = stub

    assert node._resolve_client() is stub


def test_resolve_retrieval_results_returns_empty_for_missing_entries() -> None:
    state = State(inputs={}, results={"fusion": None}, structured_response=None)
    assert _resolve_retrieval_results(state, "fusion", "results") == []


def test_resolve_retrieval_results_skips_null_items() -> None:
    entry_payload = {
        "id": "a",
        "score": 1.0,
        "text": "x",
        "metadata": {},
        "source": "source",
        "sources": ["source"],
    }
    state = State(
        inputs={},
        results={"fusion": [entry_payload, None]},
        structured_response=None,
    )

    resolved = _resolve_retrieval_results(state, "fusion", "results")

    assert len(resolved) == 1
