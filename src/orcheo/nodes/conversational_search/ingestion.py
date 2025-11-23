"""Ingestion primitives for conversational search."""

from __future__ import annotations
import asyncio
import hashlib
import inspect
from collections.abc import Callable, Iterable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import (
    Document,
    DocumentChunk,
    VectorRecord,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
)
from orcheo.nodes.registry import NodeMetadata, registry


EmbeddingFunction = Callable[[list[str]], list[list[float]]]


def deterministic_embedding_function(texts: list[str]) -> list[list[float]]:
    """Deterministic fallback embedding using SHA256 hashing."""
    embeddings: list[list[float]] = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Convert first 16 bytes to floats in [0, 1]
        vector = [byte / 255.0 for byte in digest[:16]]
        embeddings.append(vector)
    return embeddings


class RawDocumentInput(BaseModel):
    """User-supplied document payload prior to normalization."""

    id: str | None = Field(
        default=None, description="Optional caller-provided identifier"
    )
    content: str = Field(description="Raw text to ingest")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional metadata"
    )
    source: str | None = Field(
        default=None, description="Source identifier such as URL or path"
    )

    model_config = ConfigDict(extra="forbid")

    @classmethod
    def from_unknown(cls, value: Any) -> RawDocumentInput:
        """Coerce ``value`` into :class:`RawDocumentInput` or raise a clear error."""
        if isinstance(value, RawDocumentInput):
            return value
        if isinstance(value, Document):
            return cls(
                id=value.id,
                content=value.content,
                metadata=value.metadata,
                source=value.source,
            )
        if isinstance(value, str):
            return cls(content=value)
        if isinstance(value, dict):
            return cls(**value)
        msg = (
            "Unsupported document payload. Expected string, mapping, Document, "
            f"or RawDocumentInput but received {type(value).__name__}"
        )
        raise TypeError(msg)


@registry.register(
    NodeMetadata(
        name="DocumentLoaderNode",
        description="Normalize raw document payloads into validated Document objects.",
        category="conversational_search",
    )
)
class DocumentLoaderNode(TaskNode):
    """Node that converts user-provided payloads into normalized documents."""

    input_key: str = Field(
        default="documents",
        description="Key within ``state.inputs`` that may contain documents to ingest.",
    )
    documents: list[RawDocumentInput] = Field(
        default_factory=list, description="Inline documents configured on the node"
    )
    default_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata applied to every document unless overridden",
    )
    default_source: str | None = Field(
        default=None,
        description="Fallback source string applied when not supplied on a document",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Normalize inline and state-supplied payloads into documents."""
        payloads = list(self.documents)
        state_documents = state.get("inputs", {}).get(self.input_key)
        if state_documents:
            if not isinstance(state_documents, list):
                msg = "state.inputs documents must be a list"
                raise ValueError(msg)
            payloads.extend(state_documents)

        raw_inputs = [RawDocumentInput.from_unknown(value) for value in payloads]
        if not raw_inputs:
            msg = "No documents provided to DocumentLoaderNode"
            raise ValueError(msg)

        documents: list[Document] = []
        for index, raw in enumerate(raw_inputs):
            document_id = raw.id or f"{self.name}-doc-{index}"
            metadata = {**self.default_metadata, **raw.metadata}
            documents.append(
                Document(
                    id=document_id,
                    content=raw.content,
                    metadata=metadata,
                    source=raw.source or self.default_source,
                )
            )

        return {"documents": documents}


@registry.register(
    NodeMetadata(
        name="ChunkingStrategyNode",
        description="Split documents into overlapping chunks for indexing.",
        category="conversational_search",
    )
)
class ChunkingStrategyNode(TaskNode):
    """Character-based chunking strategy with configurable overlap."""

    source_result_key: str = Field(
        default="document_loader",
        description="Name of the upstream result entry containing documents.",
    )
    documents_field: str = Field(
        default="documents",
        description="Field name within the upstream results that stores documents.",
    )
    chunk_size: int = Field(
        default=800, gt=0, description="Maximum characters per chunk"
    )
    chunk_overlap: int = Field(
        default=80, ge=0, description="Overlap between sequential chunks"
    )
    preserve_metadata_keys: list[str] | None = Field(
        default=None,
        description="Optional subset of document metadata keys to propagate to chunks",
    )

    @field_validator("chunk_overlap")
    @classmethod
    def _validate_overlap(cls, value: int, info: Any) -> int:  # type: ignore[override]
        chunk_size = info.data.get("chunk_size")
        if chunk_size is not None and value >= chunk_size:
            msg = "chunk_overlap must be smaller than chunk_size"
            raise ValueError(msg)
        return value

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Split documents into overlapping chunks."""
        documents = self._resolve_documents(state)
        if not documents:
            msg = "ChunkingStrategyNode requires at least one document"
            raise ValueError(msg)

        chunks: list[DocumentChunk] = []
        for document in documents:
            start = 0
            chunk_index = 0
            while start < len(document.content):
                end = min(start + self.chunk_size, len(document.content))
                content = document.content[start:end]
                metadata = self._merge_metadata(document, chunk_index)
                chunk_id = f"{document.id}-chunk-{chunk_index}"
                chunks.append(
                    DocumentChunk(
                        id=chunk_id,
                        document_id=document.id,
                        index=chunk_index,
                        content=content,
                        metadata=metadata,
                    )
                )
                if end == len(document.content):
                    break
                start = end - self.chunk_overlap
                chunk_index += 1

        return {"chunks": chunks}

    def _resolve_documents(self, state: State) -> list[Document]:
        results = state.get("results", {})
        source = results.get(self.source_result_key, {})
        if isinstance(source, dict) and self.documents_field in source:
            documents = source[self.documents_field]
        else:
            documents = results.get(self.documents_field)
        if not documents:
            return []
        if not isinstance(documents, list):
            msg = "documents payload must be a list"
            raise ValueError(msg)
        return [Document.model_validate(doc) for doc in documents]

    def _merge_metadata(self, document: Document, chunk_index: int) -> dict[str, Any]:
        metadata = {
            "document_id": document.id,
            "chunk_index": chunk_index,
            "source": document.source,
        }
        base_metadata = document.metadata
        if self.preserve_metadata_keys is not None:
            base_metadata = {
                key: value
                for key, value in document.metadata.items()
                if key in self.preserve_metadata_keys
            }
        metadata.update(base_metadata)
        return metadata


@registry.register(
    NodeMetadata(
        name="MetadataExtractorNode",
        description="Attach structured metadata to normalized documents.",
        category="conversational_search",
    )
)
class MetadataExtractorNode(TaskNode):
    """Enrich documents with deterministic metadata for downstream filters."""

    source_result_key: str = Field(
        default="document_loader",
        description="Name of the upstream result entry containing documents.",
    )
    documents_field: str = Field(
        default="documents", description="Field name carrying documents"
    )
    static_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata added to every document as defaults",
    )
    tags: list[str] = Field(
        default_factory=list, description="Tags appended to the metadata array"
    )
    required_fields: list[str] = Field(
        default_factory=list,
        description="Metadata keys that must be present after enrichment",
    )
    infer_title_from_first_line: bool = Field(
        default=True,
        description=(
            "Populate a title from the document's first non-empty line if missing"
        ),
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Enrich documents with defaults, tags, and optional titles."""
        documents = self._resolve_documents(state)
        if not documents:
            msg = "MetadataExtractorNode requires at least one document"
            raise ValueError(msg)

        enriched: list[Document] = []
        for document in documents:
            metadata = {**self.static_metadata, **document.metadata}
            if self.tags:
                tags = list(dict.fromkeys(metadata.get("tags", []) + self.tags))
                metadata["tags"] = tags
            if self.infer_title_from_first_line and "title" not in metadata:
                title = self._first_non_empty_line(document.content)
                if title:
                    metadata["title"] = title
            for field in self.required_fields:
                if field not in metadata:
                    msg = (
                        f"Required metadata field '{field}' missing for document"
                        f" {document.id}"
                    )
                    raise ValueError(msg)
            if isinstance(document, Document):
                enriched_document = document.model_copy(update={"metadata": metadata})
            else:
                enriched_document = Document.model_construct(
                    id=document.id,
                    content=document.content,
                    metadata=metadata,
                    source=document.source,
                )
            enriched.append(enriched_document)

        return {"documents": enriched}

    def _resolve_documents(self, state: State) -> list[Document]:
        results = state.get("results", {})
        source = results.get(self.source_result_key, {})
        if isinstance(source, dict) and self.documents_field in source:
            documents = source[self.documents_field]
        else:
            documents = results.get(self.documents_field)
        if not documents:
            return []
        if not isinstance(documents, list):
            msg = "documents payload must be a list"
            raise ValueError(msg)
        return [Document.model_validate(doc) for doc in documents]

    @staticmethod
    def _first_non_empty_line(content: str) -> str | None:
        for line in content.splitlines():
            normalized = line.strip()
            if normalized:
                return normalized
        return None


@registry.register(
    NodeMetadata(
        name="EmbeddingIndexerNode",
        description=(
            "Generate embeddings for document chunks and write to a vector store."
        ),
        category="conversational_search",
    )
)
class EmbeddingIndexerNode(TaskNode):
    """Node that embeds chunks and stores them via a configurable vector store."""

    source_result_key: str = Field(
        default="chunking_strategy",
        description="Name of the upstream result entry containing chunks.",
    )
    chunks_field: str = Field(
        default="chunks", description="Field containing chunk payloads"
    )
    vector_store: BaseVectorStore = Field(
        default_factory=InMemoryVectorStore,
        description="Vector store adapter used for persistence",
    )
    embedding_function: EmbeddingFunction | None = Field(
        default=None,
        description="Callable that converts text batches into embedding vectors",
    )
    required_metadata_keys: list[str] = Field(
        default_factory=lambda: ["document_id", "chunk_index"],
        description="Metadata keys that must be present before upsert",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Embed chunks and persist vectors via the configured store."""
        chunks = self._resolve_chunks(state)
        if not chunks:
            msg = "EmbeddingIndexerNode requires at least one chunk"
            raise ValueError(msg)

        for key in self.required_metadata_keys:
            for chunk in chunks:
                if key not in chunk.metadata:
                    msg = f"Missing required metadata '{key}' for chunk {chunk.id}"
                    raise ValueError(msg)

        embeddings = await self._embed([chunk.content for chunk in chunks])
        if len(embeddings) != len(chunks):
            msg = (
                "Embedding function returned "
                f"{len(embeddings)} embeddings for {len(chunks)} chunks"
            )
            raise ValueError(msg)

        records = [
            VectorRecord(
                id=chunk.id,
                values=vector,
                text=chunk.content,
                metadata=chunk.metadata,
            )
            for chunk, vector in zip(chunks, embeddings, strict=True)
        ]
        await self.vector_store.upsert(records)

        return {
            "indexed": len(records),
            "ids": [record.id for record in records],
            "namespace": getattr(self.vector_store, "namespace", None),
        }

    def _resolve_chunks(self, state: State) -> list[DocumentChunk]:
        results = state.get("results", {})
        source = results.get(self.source_result_key, {})
        if isinstance(source, dict) and self.chunks_field in source:
            chunks = source[self.chunks_field]
        else:
            chunks = results.get(self.chunks_field)
        if not chunks:
            return []
        if not isinstance(chunks, list):
            msg = "chunks payload must be a list"
            raise ValueError(msg)
        normalized: list[DocumentChunk] = []
        for chunk in chunks:
            if isinstance(chunk, DocumentChunk):
                normalized.append(chunk)
                continue
            if isinstance(chunk, dict):
                cleaned = dict(chunk)
                cleaned.pop("token_count", None)
                normalized.append(DocumentChunk.model_validate(cleaned))
                continue
            msg = "chunks payload must contain DocumentChunk entries"
            raise ValueError(msg)
        return normalized

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        embedder = self.embedding_function or deterministic_embedding_function
        result = embedder(texts)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, list) or not all(
            isinstance(row, list) for row in result
        ):
            msg = "Embedding function must return List[List[float]]"
            raise ValueError(msg)
        return result


@registry.register(
    NodeMetadata(
        name="IncrementalIndexerNode",
        description=(
            "Index new or updated chunks in batches with retry and deduplication."
        ),
        category="conversational_search",
    )
)
class IncrementalIndexerNode(TaskNode):
    """Index chunks incrementally with retries and backpressure controls."""

    source_result_key: str = Field(
        default="chunking_strategy",
        description="Name of the upstream result entry containing chunks.",
    )
    chunks_field: str = Field(
        default="chunks", description="Field containing chunk payloads"
    )
    vector_store: BaseVectorStore = Field(
        default_factory=InMemoryVectorStore,
        description="Vector store adapter used for persistence",
    )
    embedding_function: EmbeddingFunction | None = Field(
        default=None,
        description="Callable that converts text batches into embedding vectors",
    )
    batch_size: int = Field(
        default=64, gt=0, description="Maximum records processed per upsert batch"
    )
    max_retries: int = Field(
        default=2, ge=0, description="Number of retry attempts for failed batches"
    )
    backoff_seconds: float = Field(
        default=0.05,
        ge=0.0,
        description="Base delay between retries for failed batches",
    )
    deduplicate: bool = Field(
        default=True,
        description="Skip chunks that have already been indexed by this node instance",
    )

    indexed_ids: set[str] = Field(default_factory=set)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Embed unseen chunks and persist them in batches with retries."""
        chunks = self._resolve_chunks(state)
        if not chunks:
            msg = "IncrementalIndexerNode requires at least one chunk"
            raise ValueError(msg)

        pending: list[DocumentChunk] = []
        for chunk in chunks:
            if self.deduplicate and chunk.id in self.indexed_ids:
                continue
            pending.append(chunk)

        if not pending:
            return {"indexed": 0, "skipped": len(chunks), "ids": []}

        embeddings = await self._embed([chunk.content for chunk in pending])
        if len(embeddings) != len(pending):
            msg = (
                "Embedding function returned "
                f"{len(embeddings)} embeddings for {len(pending)} chunks"
            )
            raise ValueError(msg)

        records = [
            VectorRecord(
                id=chunk.id,
                values=vector,
                text=chunk.content,
                metadata=chunk.metadata,
            )
            for chunk, vector in zip(pending, embeddings, strict=True)
        ]

        await self._upsert_in_batches(records)
        for record in records:
            self.indexed_ids.add(record.id)

        return {
            "indexed": len(records),
            "skipped": len(chunks) - len(pending),
            "ids": [record.id for record in records],
        }

    async def _upsert_in_batches(self, records: list[VectorRecord]) -> None:
        for start in range(0, len(records), self.batch_size):
            batch = records[start : start + self.batch_size]
            await self._retry_with_backoff(self.vector_store.upsert, batch)

    async def _retry_with_backoff(
        self, func: Callable[[Iterable[VectorRecord]], Any], batch: list[VectorRecord]
    ) -> None:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                await func(batch)
                return
            except Exception as exc:  # pragma: no cover - tested via retries
                last_error = exc
                if attempt == self.max_retries:
                    raise
                delay = self.backoff_seconds * (2**attempt)
                await asyncio.sleep(delay)
        if last_error:
            raise last_error

    def _resolve_chunks(self, state: State) -> list[DocumentChunk]:
        results = state.get("results", {})
        source = results.get(self.source_result_key, {})
        if isinstance(source, dict) and self.chunks_field in source:
            chunks = source[self.chunks_field]
        else:
            chunks = results.get(self.chunks_field)
        if not chunks:
            return []
        if not isinstance(chunks, list):
            msg = "chunks payload must be a list"
            raise ValueError(msg)
        normalized: list[DocumentChunk] = []
        for chunk in chunks:
            if isinstance(chunk, DocumentChunk):
                normalized.append(chunk)
                continue
            if isinstance(chunk, dict):
                cleaned = dict(chunk)
                cleaned.pop("token_count", None)
                normalized.append(DocumentChunk.model_validate(cleaned))
                continue
            msg = "chunks payload must contain DocumentChunk entries"
            raise ValueError(msg)
        return normalized

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        embedder = self.embedding_function or deterministic_embedding_function
        result = embedder(texts)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, list) or not all(
            isinstance(row, list) for row in result
        ):
            msg = "Embedding function must return List[List[float]]"
            raise ValueError(msg)
        return result
