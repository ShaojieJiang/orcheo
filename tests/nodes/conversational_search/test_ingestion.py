"""Unit tests for conversational search ingestion primitives."""

import pytest

from orcheo.graph.state import State
from orcheo.nodes.conversational_search.ingestion import (
    ChunkingStrategyNode,
    DocumentLoaderNode,
    EmbeddingIndexerNode,
    MetadataExtractorNode,
    RawDocumentInput,
)
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


@pytest.mark.asyncio
async def test_document_loader_combines_inline_and_state_documents() -> None:
    node = DocumentLoaderNode(
        name="document_loader",
        documents=[RawDocumentInput(content="Inline doc")],
        default_source="inline",
        default_metadata={"project": "conversational"},
    )
    state = State(
        inputs={
            "documents": [
                "State provided",
                {"content": "Third", "metadata": {"team": "ml"}},
            ]
        },
        results={},
        structured_response=None,
    )

    result = await node.run(state, {})

    documents = result["documents"]
    assert len(documents) == 3
    assert {doc.source for doc in documents} == {"inline"}
    assert documents[1].metadata["project"] == "conversational"
    assert documents[2].metadata["team"] == "ml"


@pytest.mark.asyncio
async def test_chunking_strategy_creates_overlapping_chunks() -> None:
    loader_result = {
        "documents": [
            {
                "id": "doc-1",
                "content": "abcdefghij",  # 10 chars
                "metadata": {"genre": "demo"},
            }
        ]
    }
    state = State(
        inputs={}, results={"document_loader": loader_result}, structured_response=None
    )
    node = ChunkingStrategyNode(name="chunking_strategy", chunk_size=4, chunk_overlap=2)

    result = await node.run(state, {})

    chunks = result["chunks"]
    assert [chunk.content for chunk in chunks] == ["abcd", "cdef", "efgh", "ghij"]
    assert all(chunk.metadata["document_id"] == "doc-1" for chunk in chunks)
    assert chunks[0].metadata["genre"] == "demo"


@pytest.mark.asyncio
async def test_metadata_extractor_merges_tags_and_title() -> None:
    loader_result = {
        "documents": [
            {
                "id": "doc-1",
                "content": "Title line\nBody text",
                "metadata": {"existing": True, "tags": ["source"]},
            }
        ]
    }
    state = State(
        inputs={}, results={"document_loader": loader_result}, structured_response=None
    )
    node = MetadataExtractorNode(
        name="metadata_extractor",
        static_metadata={"audience": "internal"},
        tags=["conversational"],
        required_fields=["audience", "title"],
    )

    result = await node.run(state, {})

    document = result["documents"][0]
    assert document.metadata["audience"] == "internal"
    assert document.metadata["existing"] is True
    assert document.metadata["title"] == "Title line"
    assert document.metadata["tags"] == ["source", "conversational"]


@pytest.mark.asyncio
async def test_embedding_indexer_uses_default_embedder_and_in_memory_store() -> None:
    chunks = {
        "chunks": [
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "index": 0,
                "content": "chunk text",
                "metadata": {"document_id": "doc-1", "chunk_index": 0},
            }
        ]
    }
    vector_store = InMemoryVectorStore()
    state = State(
        inputs={}, results={"chunking_strategy": chunks}, structured_response=None
    )
    node = EmbeddingIndexerNode(name="embedding_indexer", vector_store=vector_store)

    result = await node.run(state, {})

    assert result["indexed"] == 1
    assert "chunk-1" in vector_store.records
    stored = vector_store.records["chunk-1"]
    assert len(stored.values) == 16
    assert stored.metadata["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_embedding_indexer_raises_on_embedding_length_mismatch() -> None:
    chunks = {
        "chunks": [
            {
                "id": "chunk-1",
                "document_id": "doc-1",
                "index": 0,
                "content": "chunk one",
                "metadata": {"document_id": "doc-1", "chunk_index": 0},
            },
            {
                "id": "chunk-2",
                "document_id": "doc-1",
                "index": 1,
                "content": "chunk two",
                "metadata": {"document_id": "doc-1", "chunk_index": 1},
            },
        ]
    }
    vector_store = InMemoryVectorStore()
    state = State(
        inputs={}, results={"chunking_strategy": chunks}, structured_response=None
    )

    def short_embedding_function(texts: list[str]) -> list[list[float]]:
        return [[0.0] * 4 for _ in texts[:1]]

    node = EmbeddingIndexerNode(
        name="embedding_indexer",
        vector_store=vector_store,
        embedding_function=short_embedding_function,
    )

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 chunks"):
        await node.run(state, {})

    assert vector_store.records == {}


@pytest.mark.asyncio
async def test_pinecone_vector_store_dependency_error_message() -> None:
    from orcheo.nodes.conversational_search.vector_store import PineconeVectorStore

    store = PineconeVectorStore(index_name="missing-client")
    with pytest.raises(ImportError):
        await store.upsert([])
