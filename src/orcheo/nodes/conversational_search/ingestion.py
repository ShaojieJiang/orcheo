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
    content: str | None = Field(
        default=None,
        description="Raw text to ingest (optional if storage_path provided)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional metadata"
    )
    source: str | None = Field(
        default=None, description="Source identifier such as URL or path"
    )
    storage_path: str | None = Field(
        default=None,
        description="Path to file on disk containing document content",
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
        from pathlib import Path

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

            # Read content from storage_path if provided, otherwise use content
            content = raw.content
            if raw.storage_path:
                storage_path = Path(raw.storage_path)
                if not storage_path.exists():
                    msg = f"Storage path does not exist: {raw.storage_path}"
                    raise FileNotFoundError(msg)
                # Read and decode file content
                raw_bytes = storage_path.read_bytes()
                try:
                    content = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    content = raw_bytes.decode("latin-1")

            if not content:
                msg = (
                    f"Document {document_id} has no content. "
                    "Provide either 'content' or 'storage_path'."
                )
                raise ValueError(msg)

            documents.append(
                Document(
                    id=document_id,
                    content=content,
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
        return [DocumentChunk.model_validate(chunk) for chunk in chunks]

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
            "Index or update chunks incrementally with retry and backpressure controls."
        ),
        category="conversational_search",
    )
)
class IncrementalIndexerNode(TaskNode):
    """Embed and upsert chunk embeddings while skipping unchanged payloads."""

    source_result_key: str = Field(
        default="chunking_strategy",
        description="Upstream result entry containing chunk payloads.",
    )
    chunks_field: str = Field(
        default="chunks", description="Field under the result containing chunks"
    )
    vector_store: BaseVectorStore = Field(
        default_factory=InMemoryVectorStore,
        description="Vector store adapter used for upserts.",
    )
    embedding_function: EmbeddingFunction | None = Field(
        default=None,
        description="Optional embedding callable applied to chunk content.",
    )
    batch_size: int = Field(default=32, gt=0, description="Chunk batch size")
    max_retries: int = Field(default=2, ge=0, description="Retry attempts")
    backoff_seconds: float = Field(
        default=0.05, ge=0.0, description="Base backoff for retry attempts"
    )
    skip_unchanged: bool = Field(
        default=True,
        description="Skip upserts when the stored content hash matches the new hash.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Embed and upsert chunks with retry and change-detection."""
        chunks = self._resolve_chunks(state)
        if not chunks:
            msg = "IncrementalIndexerNode requires at least one chunk"
            raise ValueError(msg)

        upserted_ids: list[str] = []
        skipped = 0
        for start in range(0, len(chunks), self.batch_size):
            batch = chunks[start : start + self.batch_size]
            embeddings = await self._embed([chunk.content for chunk in batch])

            records: list[VectorRecord] = []
            for chunk, vector in zip(batch, embeddings, strict=True):
                content_hash = self._hash_text(chunk.content)
                if self.skip_unchanged and self._is_unchanged(chunk.id, content_hash):
                    skipped += 1
                    continue

                metadata = {
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.index,
                    "content_hash": content_hash,
                }
                metadata.update(chunk.metadata)
                records.append(
                    VectorRecord(
                        id=chunk.id,
                        values=vector,
                        text=chunk.content,
                        metadata=metadata,
                    )
                )

            if records:
                await self._upsert_with_retry(records)
                upserted_ids.extend(record.id for record in records)

        return {
            "indexed_count": len(upserted_ids),
            "skipped": skipped,
            "upserted_ids": upserted_ids,
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
        return [DocumentChunk.model_validate(chunk) for chunk in chunks]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        embedder = self.embedding_function or deterministic_embedding_function
        output = embedder(texts)
        if inspect.isawaitable(output):
            output = await output
        if not isinstance(output, list) or not all(
            isinstance(row, list) for row in output
        ):
            msg = "Embedding function must return List[List[float]]"
            raise ValueError(msg)
        return output

    def _is_unchanged(self, record_id: str, content_hash: str) -> bool:
        store_records = getattr(self.vector_store, "records", None)
        if not isinstance(store_records, dict):
            return False
        existing = store_records.get(record_id)
        if existing is None:
            return False
        return existing.metadata.get("content_hash") == content_hash

    def _hash_text(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    async def _upsert_with_retry(self, records: Iterable[VectorRecord]) -> None:
        for attempt in range(self.max_retries + 1):  # pragma: no branch
            try:
                await self.vector_store.upsert(records)
                return
            except Exception as exc:  # pragma: no cover - exercised via tests
                if attempt == self.max_retries:
                    msg = "Vector store upsert failed after retries"
                    raise RuntimeError(msg) from exc
                await asyncio.sleep(self.backoff_seconds * (2**attempt))
