"""Unit tests for conversational search ingestion primitives."""

from __future__ import annotations
import pytest
from orcheo.graph.state import State
from orcheo.nodes.conversational_search.ingestion import (
    ChunkingStrategyNode,
    DocumentLoaderNode,
    EmbeddingIndexerNode,
    MetadataExtractorNode,
    RawDocumentInput,
)
from orcheo.nodes.conversational_search.models import Document
from orcheo.nodes.conversational_search.vector_store import InMemoryVectorStore


class _FakeDocument:
    """Minimal doc-like object that bypasses :class:`Document` validation."""

    def __init__(
        self,
        id: str,
        content: str,
        metadata: dict[str, object] | None = None,
        source: str | None = None,
    ) -> None:
        self.id = id
        self.content = content
        self.metadata = metadata or {}
        self.source = source


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


def test_raw_document_input_accepts_document_payload() -> None:
    document = Document(
        id="doc-raw",
        content="normalized content",
        metadata={"team": "ai"},
        source="unit",
    )
    raw = RawDocumentInput.from_unknown(document)
    assert raw.id == "doc-raw"
    assert raw.metadata["team"] == "ai"
    assert raw.source == "unit"


def test_raw_document_input_rejects_invalid_payload_type() -> None:
    with pytest.raises(TypeError, match="Unsupported document payload"):
        RawDocumentInput.from_unknown(123)


@pytest.mark.asyncio
async def test_document_loader_rejects_non_list_state_documents() -> None:
    node = DocumentLoaderNode(name="document_loader")
    state = State(
        inputs={"documents": "not-a-list"},
        results={},
        structured_response=None,
    )

    with pytest.raises(ValueError, match="state.inputs documents must be a list"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_document_loader_requires_at_least_one_document() -> None:
    node = DocumentLoaderNode(name="document_loader")
    state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(ValueError, match="No documents provided to DocumentLoaderNode"):
        await node.run(state, {})


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


def test_chunking_strategy_validates_chunk_overlap() -> None:
    with pytest.raises(
        ValueError, match="chunk_overlap must be smaller than chunk_size"
    ):
        ChunkingStrategyNode(
            name="chunking_strategy",
            chunk_size=3,
            chunk_overlap=3,
        )


@pytest.mark.asyncio
async def test_chunking_strategy_requires_documents() -> None:
    node = ChunkingStrategyNode(name="chunking_strategy")
    state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="ChunkingStrategyNode requires at least one document"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_chunking_strategy_resolves_documents_from_root_results() -> None:
    state = State(
        inputs={},
        results={
            "document_loader": {},
            "documents": [
                {
                    "id": "root-doc",
                    "content": "abcdef",
                    "metadata": {"genre": "root"},
                    "source": "root",
                }
            ],
        },
        structured_response=None,
    )
    node = ChunkingStrategyNode(name="chunking_strategy", chunk_size=4, chunk_overlap=1)

    result = await node.run(state, {})

    assert result["chunks"][0].document_id == "root-doc"
    assert result["chunks"][0].metadata["genre"] == "root"


@pytest.mark.asyncio
async def test_chunking_strategy_rejects_non_list_document_payload() -> None:
    state = State(
        inputs={},
        results={"document_loader": {"documents": "invalid"}},
        structured_response=None,
    )
    node = ChunkingStrategyNode(name="chunking_strategy")

    with pytest.raises(ValueError, match="documents payload must be a list"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_chunking_strategy_preserves_selected_metadata_keys() -> None:
    state = State(
        inputs={},
        results={
            "document_loader": {
                "documents": [
                    {
                        "id": "doc-keep",
                        "content": "abcdef",
                        "metadata": {"keep": "yes", "drop": "no"},
                        "source": "kept",
                    }
                ]
            }
        },
        structured_response=None,
    )
    node = ChunkingStrategyNode(
        name="chunking_strategy",
        chunk_size=6,
        chunk_overlap=1,
        preserve_metadata_keys=["keep"],
    )

    result = await node.run(state, {})
    metadata = result["chunks"][0].metadata
    assert metadata["keep"] == "yes"
    assert "drop" not in metadata


@pytest.mark.asyncio
async def test_chunking_strategy_handles_empty_documents() -> None:
    state = State(inputs={}, results={}, structured_response=None)
    node = ChunkingStrategyNode(name="chunking_strategy")
    fake_doc = _FakeDocument(id="empty-doc", content="", metadata={}, source="empty")
    node._resolve_documents = lambda _: [fake_doc]

    result = await node.run(state, {})

    assert result["chunks"] == []


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
async def test_metadata_extractor_requires_documents() -> None:
    node = MetadataExtractorNode(name="metadata_extractor")
    state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="MetadataExtractorNode requires at least one document"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_metadata_extractor_rejects_non_list_documents_payload() -> None:
    state = State(
        inputs={},
        results={"document_loader": {"documents": "invalid"}},
        structured_response=None,
    )
    node = MetadataExtractorNode(name="metadata_extractor")

    with pytest.raises(ValueError, match="documents payload must be a list"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_metadata_extractor_enforces_required_fields() -> None:
    state = State(
        inputs={},
        results={
            "document_loader": {
                "documents": [
                    {
                        "id": "doc-req",
                        "content": "body text",
                        "metadata": {},
                    }
                ]
            }
        },
        structured_response=None,
    )
    node = MetadataExtractorNode(
        name="metadata_extractor",
        required_fields=["audience"],
    )

    with pytest.raises(ValueError, match="Required metadata field 'audience' missing"):
        await node.run(state, {})


def test_metadata_extractor_skips_empty_lines_when_infering_title() -> None:
    assert MetadataExtractorNode._first_non_empty_line("\n   \n") is None


@pytest.mark.asyncio
async def test_metadata_extractor_skips_title_inference_when_disabled() -> None:
    state = State(inputs={}, results={}, structured_response=None)
    node = MetadataExtractorNode(
        name="metadata_extractor",
        infer_title_from_first_line=False,
    )
    fake_doc = _FakeDocument(
        id="doc-no-infer", content="First line\nSecond line", metadata={}
    )
    node._resolve_documents = lambda _: [fake_doc]

    result = await node.run(state, {})

    assert "title" not in result["documents"][0].metadata


@pytest.mark.asyncio
async def test_metadata_extractor_does_not_add_title_for_blank_content() -> None:
    state = State(inputs={}, results={}, structured_response=None)
    node = MetadataExtractorNode(name="metadata_extractor")
    fake_doc = _FakeDocument(id="doc-blank", content="\n\n", metadata={})
    node._resolve_documents = lambda _: [fake_doc]

    result = await node.run(state, {})

    assert "title" not in result["documents"][0].metadata


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
async def test_embedding_indexer_requires_chunks() -> None:
    node = EmbeddingIndexerNode(
        name="embedding_indexer", vector_store=InMemoryVectorStore()
    )
    state = State(inputs={}, results={}, structured_response=None)

    with pytest.raises(
        ValueError, match="EmbeddingIndexerNode requires at least one chunk"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_embedding_indexer_detects_missing_metadata_key() -> None:
    state = State(
        inputs={},
        results={
            "chunking_strategy": {
                "chunks": [
                    {
                        "id": "chunk-1",
                        "document_id": "doc-1",
                        "index": 0,
                        "content": "chunk content",
                        "metadata": {"chunk_index": 0},
                    }
                ]
            }
        },
        structured_response=None,
    )
    node = EmbeddingIndexerNode(name="embedding_indexer")

    with pytest.raises(
        ValueError, match="Missing required metadata 'document_id' for chunk chunk-1"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_embedding_indexer_rejects_non_list_chunks_payload() -> None:
    state = State(
        inputs={},
        results={"chunking_strategy": {"chunks": "invalid"}},
        structured_response=None,
    )
    node = EmbeddingIndexerNode(name="embedding_indexer")

    with pytest.raises(ValueError, match="chunks payload must be a list"):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_embedding_indexer_accepts_async_embedding_function() -> None:
    async def embed(texts: list[str]) -> list[list[float]]:
        return [[float(len(text))] for text in texts]

    chunks_payload = {
        "chunks": [
            {
                "id": "chunk-async",
                "document_id": "doc-async",
                "index": 0,
                "content": "chunk async",
                "metadata": {"document_id": "doc-async", "chunk_index": 0},
            }
        ]
    }
    vector_store = InMemoryVectorStore()
    node = EmbeddingIndexerNode(
        name="embedding_indexer",
        vector_store=vector_store,
        embedding_function=embed,
    )
    state = State(
        inputs={},
        results={"chunking_strategy": chunks_payload},
        structured_response=None,
    )

    result = await node.run(state, {})

    assert result["indexed"] == 1
    assert vector_store.records["chunk-async"].values == [float(len("chunk async"))]


@pytest.mark.asyncio
async def test_embedding_indexer_rejects_invalid_embedding_response() -> None:
    def embed(texts: list[str]) -> str:
        return "invalid"

    state = State(
        inputs={},
        results={
            "chunking_strategy": {
                "chunks": [
                    {
                        "id": "chunk-invalid",
                        "document_id": "doc-invalid",
                        "index": 0,
                        "content": "chunk invalid",
                        "metadata": {"document_id": "doc-invalid", "chunk_index": 0},
                    }
                ]
            }
        },
        structured_response=None,
    )
    node = EmbeddingIndexerNode(
        name="embedding_indexer",
        embedding_function=embed,
    )

    with pytest.raises(
        ValueError, match="Embedding function must return List\\[List\\[float\\]\\]"
    ):
        await node.run(state, {})


@pytest.mark.asyncio
async def test_pinecone_vector_store_dependency_error_message() -> None:
    from orcheo.nodes.conversational_search.vector_store import PineconeVectorStore

    store = PineconeVectorStore(index_name="missing-client")
    with pytest.raises(ImportError):
        await store.upsert([])
