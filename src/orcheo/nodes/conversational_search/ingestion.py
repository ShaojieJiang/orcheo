"""Ingestion primitives for conversational search."""

from __future__ import annotations
import asyncio
import contextlib
import hashlib
import inspect
import os
from collections.abc import Awaitable, Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, ConfigDict, Field, field_validator
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import (
    Document,
    DocumentChunk,
    SparseValues,
    VectorRecord,
)
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
)
from orcheo.nodes.registry import NodeMetadata, registry


@dataclass
class EmbeddingVector:
    """Normalized embedding output supporting dense and sparse values."""

    values: list[float]
    sparse_values: SparseValues | None = None


EmbeddingResult = list[list[float]] | list[EmbeddingVector] | list[dict[str, Any]]
EmbeddingMethod = Callable[[list[str]], EmbeddingResult | Awaitable[EmbeddingResult]]

_EMBEDDING_METHODS: dict[str, EmbeddingMethod] = {}


def register_embedding_method(name: str, method: EmbeddingMethod) -> EmbeddingMethod:
    """Register an embedding callable for later resolution."""
    _EMBEDDING_METHODS[name] = method
    return method


def resolve_embedding_method(name: str) -> EmbeddingMethod:
    """Return the callable tied to ``name`` or raise ``ValueError``."""
    try:
        return _EMBEDDING_METHODS[name]
    except KeyError as exc:  # pragma: no cover - failure path exercised in tests
        raise ValueError(f"Unknown embedding method '{name}'") from exc


def _coerce_float_list(values: Any) -> list[float]:
    if not isinstance(values, list):
        msg = "embedding value payload must be a list of floats"
        raise ValueError(msg)
    normalized: list[float] = []
    for item in values:
        if not isinstance(item, int | float):
            msg = "embedding value payload must only contain numbers"
            raise ValueError(msg)
        normalized.append(float(item))
    return normalized


def _coerce_sparse_values(payload: Any) -> SparseValues:
    if isinstance(payload, SparseValues):
        return payload
    if not isinstance(payload, dict):
        msg = "sparse embedding payload must be a mapping"
        raise ValueError(msg)
    return SparseValues.model_validate(payload)


def normalize_embedding_output(result: Any) -> list[EmbeddingVector]:
    """Normalize embedding responses into ``EmbeddingVector`` entries."""
    if not isinstance(result, list):
        msg = "embedding response must be a list"
        raise ValueError(msg)

    normalized: list[EmbeddingVector] = []
    for entry in result:
        if isinstance(entry, EmbeddingVector):
            normalized.append(entry)
            continue
        if isinstance(entry, list):
            normalized.append(EmbeddingVector(values=_coerce_float_list(entry)))
            continue
        if isinstance(entry, dict):
            sparse_payload = entry.get("sparse_values")
            sparse = (
                None
                if sparse_payload is None
                else _coerce_sparse_values(sparse_payload)
            )
            dense_values = entry.get("values")
            if dense_values is None:
                values: list[float] = []
            else:
                values = _coerce_float_list(dense_values)
            if not values and sparse is None:
                msg = "embedding payload must include dense or sparse values"
                raise ValueError(msg)
            normalized.append(EmbeddingVector(values=values, sparse_values=sparse))
            continue
        msg = "embedding payload entries must be lists or mappings"
        raise ValueError(msg)
    return normalized


@contextlib.contextmanager
def _temporary_env_vars(env_vars: dict[str, str | None]) -> Iterator[None]:
    """Temporarily install environment variables for embedding execution."""
    if not env_vars:
        yield
        return
    previous: dict[str, str | None] = {}
    for key, value in env_vars.items():
        previous[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def require_dense_embeddings(vectors: list[EmbeddingVector]) -> list[list[float]]:
    """Ensure each embedding vector contains dense values."""
    dense_values: list[list[float]] = []
    for vector in vectors:
        if not vector.values:
            msg = "dense embeddings must include non-empty float values"
            raise ValueError(msg)
        dense_values.append(vector.values)
    return dense_values


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
        payloads = list(self.documents)
        state_documents = state.get("inputs", {}).get(self.input_key)
        if state_documents:
            if not isinstance(state_documents, list):
                msg = "state.inputs documents must be a list"
                raise ValueError(msg)
            payloads.extend(state_documents)

        raw_inputs = [RawDocumentInput.from_unknown(value) for value in payloads]
        raw_inputs = self._expand_storage_paths(raw_inputs)
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
            assert content is not None

            documents.append(
                Document(
                    id=document_id,
                    content=content,
                    metadata=metadata,
                    source=raw.source or self.default_source,
                )
            )

        serialized_documents = [document.model_dump() for document in documents]
        return {"documents": serialized_documents}

    def _expand_storage_paths(
        self,
        raw_inputs: list[RawDocumentInput],
    ) -> list[RawDocumentInput]:
        """Expand directory storage paths into per-file document payloads."""
        expanded: list[RawDocumentInput] = []
        for raw in raw_inputs:
            storage_path = raw.storage_path
            if not storage_path:
                expanded.append(raw)
                continue

            path = Path(storage_path)
            if path.is_dir():
                for child in sorted(path.iterdir(), key=lambda entry: entry.name):
                    if not child.is_file():
                        continue
                    expanded.append(
                        RawDocumentInput(
                            storage_path=str(child),
                            metadata=dict(raw.metadata),
                            source=raw.source or child.name,
                        )
                    )
            else:
                expanded.append(raw)
        return expanded


class _HTMLTextExtractor(HTMLParser):
    """Simple HTML parser that extracts text content."""

    SKIP_TAGS = frozenset({"script", "style", "head", "noscript"})

    def __init__(self) -> None:
        super().__init__()
        self._text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._text_parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._text_parts)


class _HTMLTitleExtractor(HTMLParser):
    """HTML parser that extracts the document title."""

    def __init__(self) -> None:
        super().__init__()
        self._title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            stripped = data.strip()
            if stripped:
                self._title_parts.append(stripped)

    def get_title(self) -> str:
        return " ".join(self._title_parts).strip()


def _html_to_text(html: str) -> str:
    """Extract plain text from HTML content."""
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser.get_text()


def _html_to_title(html: str) -> str:
    """Extract the title text from HTML content."""
    parser = _HTMLTitleExtractor()
    parser.feed(html)
    return parser.get_title()


class WebDocumentInput(BaseModel):
    """URL-based document input for web page ingestion."""

    url: str = Field(description="URL of the web page to fetch")
    id: str | None = Field(
        default=None, description="Optional caller-provided identifier"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Optional metadata"
    )

    model_config = ConfigDict(extra="forbid")


@registry.register(
    NodeMetadata(
        name="WebDocumentLoaderNode",
        description="Fetch web pages and convert them to normalized Document objects.",
        category="conversational_search",
    )
)
class WebDocumentLoaderNode(TaskNode):
    """Node that fetches web pages and converts them to documents."""

    input_key: str = Field(
        default="urls",
        description="Key within ``state.inputs`` that may contain URLs to fetch.",
    )
    urls: list[WebDocumentInput] | str = Field(
        default_factory=list, description="Inline URLs configured on the node"
    )
    default_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata applied to every document unless overridden",
    )
    timeout: float | str = Field(
        default=30.0, description="Timeout in seconds for HTTP requests"
    )
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")
    extract_title: bool = Field(
        default=True,
        description="Extract and store the HTML <title> as metadata when missing.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Fetch web pages and convert them to normalized documents."""
        payloads = self._collect_url_payloads(state)
        if not payloads:
            msg = "No URLs provided to WebDocumentLoaderNode"
            raise ValueError(msg)

        documents: list[Document] = []
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=self.follow_redirects,
        ) as client:
            for index, web_input in enumerate(payloads):
                document = await self._fetch_document(client, web_input, index)
                documents.append(document)

        serialized_documents = [document.model_dump() for document in documents]
        return {"documents": serialized_documents}

    def _collect_url_payloads(self, state: State) -> list[WebDocumentInput]:
        """Collect URL payloads from inline config and state inputs."""
        inline = self.urls if isinstance(self.urls, list) else []
        payloads = [self._coerce_url_input(item) for item in inline]
        state_urls = state.get("inputs", {}).get(self.input_key)
        if not state_urls:
            return payloads
        if not isinstance(state_urls, list):
            msg = "state.inputs urls must be a list"
            raise ValueError(msg)
        for item in state_urls:
            payloads.append(self._coerce_url_input(item))
        return payloads

    def _coerce_url_input(self, item: Any) -> WebDocumentInput:
        """Coerce an item into a WebDocumentInput."""
        if isinstance(item, str):
            return WebDocumentInput(url=item)
        if isinstance(item, dict):
            return WebDocumentInput(**item)
        if isinstance(item, WebDocumentInput):
            return item
        msg = f"Unsupported URL payload type: {type(item).__name__}"
        raise TypeError(msg)

    async def _fetch_document(
        self,
        client: httpx.AsyncClient,
        web_input: WebDocumentInput,
        index: int,
    ) -> Document:
        """Fetch a single URL and convert it to a Document."""
        try:
            response = await client.get(web_input.url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            msg = f"Failed to fetch URL {web_input.url}: {exc!s}"
            raise ValueError(msg) from exc

        text_content = _html_to_text(response.text)
        if not text_content.strip():
            msg = f"No text content extracted from URL: {web_input.url}"
            raise ValueError(msg)

        document_id = web_input.id or f"{self.name}-doc-{index}"
        metadata = {**self.default_metadata, **web_input.metadata}
        if self.extract_title and "title" not in metadata:
            title = _html_to_title(response.text)
            if title:
                metadata["title"] = title

        return Document(
            id=document_id,
            content=text_content,
            metadata=metadata,
            source=web_input.url,
        )


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
    chunk_size: int | str = Field(
        default=800, description="Maximum characters per chunk"
    )
    chunk_overlap: int | str = Field(
        default=80, description="Overlap between sequential chunks"
    )
    preserve_metadata_keys: list[str] | None = Field(
        default=None,
        description="Optional subset of document metadata keys to propagate to chunks",
    )

    @field_validator("chunk_overlap")
    @classmethod
    def _validate_overlap(cls, value: int | str, info: Any) -> int | str:  # type: ignore[override]
        chunk_size = info.data.get("chunk_size")
        if (
            isinstance(value, int)
            and isinstance(chunk_size, int)
            and value >= chunk_size
        ):
            msg = "chunk_overlap must be smaller than chunk_size"
            raise ValueError(msg)
        return value

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Split documents into overlapping chunks."""
        documents = self._resolve_documents(state)
        if not documents:
            msg = "ChunkingStrategyNode requires at least one document"
            raise ValueError(msg)

        chunk_size = int(self.chunk_size)
        chunk_overlap = int(self.chunk_overlap)

        chunks: list[DocumentChunk] = []
        for document in documents:
            start = 0
            chunk_index = 0
            while start < len(document.content):
                end = min(start + chunk_size, len(document.content))
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
                start = end - chunk_overlap
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
        name="ChunkEmbeddingNode",
        description=(
            "Generate vector records for document chunks via "
            "configurable embedding functions."
        ),
        category="conversational_search",
    )
)
class ChunkEmbeddingNode(TaskNode):
    """Embed document chunks through one or more embedding functions."""

    source_result_key: str = Field(
        default="chunking_strategy",
        description="Name of the upstream result entry containing chunks.",
    )
    chunks_field: str = Field(
        default="chunks", description="Field containing chunk payloads"
    )
    embedding_methods: dict[str, str] = Field(
        ...,
        description="Named embedding method identifiers used to transform chunk text.",
    )
    required_metadata_keys: list[str] = Field(
        default_factory=lambda: ["document_id", "chunk_index"],
        description=(
            "Metadata keys that must be present before embeddings are computed."
        ),
    )
    credential_env_vars: dict[str, str | None] = Field(
        default_factory=dict,
        description="Environment variables applied during embedding execution.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @field_validator("embedding_methods")
    @classmethod
    def _validate_embedding_methods(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("At least one embedding method must be configured")
        for method_name in value.values():
            if method_name not in _EMBEDDING_METHODS:
                raise ValueError(f"Unknown embedding method '{method_name}'")
        return value

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Convert chunks into vector records keyed by embedding name."""
        chunks = self._resolve_chunks(state)
        if not chunks:
            msg = "ChunkEmbeddingNode requires at least one chunk"
            raise ValueError(msg)

        for key in self.required_metadata_keys:
            for chunk in chunks:
                if key not in chunk.metadata:
                    msg = f"Missing required metadata '{key}' for chunk {chunk.id}"
                    raise ValueError(msg)

        records_by_function: dict[str, list[VectorRecord]] = {}
        chunk_texts = [chunk.content for chunk in chunks]
        multiple_functions = len(self.embedding_methods) > 1

        with _temporary_env_vars(self.credential_env_vars):
            for name, method_name in self.embedding_methods.items():
                embedding_function = resolve_embedding_method(method_name)
                embeddings = await self._embed(chunk_texts, embedding_function)
                if len(embeddings) != len(chunks):
                    msg = (
                        "Embedding function returned "
                        f"{len(embeddings)} embeddings for {len(chunks)} chunks"
                    )
                    raise ValueError(msg)

                records: list[VectorRecord] = []
                suffix = f"-{name}" if multiple_functions else ""
                for chunk, vector in zip(chunks, embeddings, strict=True):
                    metadata = dict(chunk.metadata)
                    metadata.setdefault("chunk_id", chunk.id)
                    metadata["embedding_type"] = name
                    record_id = f"{chunk.id}{suffix}" if suffix else chunk.id
                    records.append(
                        VectorRecord(
                            id=record_id,
                            values=vector.values,
                            text=chunk.content,
                            metadata=metadata,
                            sparse_values=vector.sparse_values,
                        )
                    )
                records_by_function[name] = records

        return {"chunk_embeddings": records_by_function}

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

    async def _embed(
        self,
        texts: list[str],
        embedder: EmbeddingMethod,
    ) -> list[EmbeddingVector]:
        result = embedder(texts)
        if inspect.isawaitable(result):
            result = await result
        try:
            return normalize_embedding_output(result)
        except ValueError as exc:
            raise ValueError(EMBEDDING_PAYLOAD_ERROR) from exc


@registry.register(
    NodeMetadata(
        name="TextEmbeddingNode",
        description=(
            "Embed one or more text inputs using a configurable embedding method."
        ),
        category="conversational_search",
    )
)
class TextEmbeddingNode(TaskNode):
    """Embed one or more text inputs from state or inputs."""

    input_key: str = Field(
        default="text",
        description="Key within state or state.inputs containing the text payload.",
    )
    embedding_method: str = Field(
        ...,
        description="Embedding method identifier applied to the text inputs.",
    )
    embedding_method_key: str = Field(
        default="embedding_method",
        description=(
            "Optional configurable key used to override the embedding method."
        ),
    )
    output_key: str = Field(
        default="embeddings",
        description="Key used to store normalized embedding outputs.",
    )
    dense_output_key: str | None = Field(
        default=None,
        description="Optional key used to store dense vector outputs.",
    )
    text_output_key: str | None = Field(
        default=None,
        description="Optional key used to store the original text payload.",
    )
    allow_empty: bool = Field(
        default=False,
        description="Whether empty or missing inputs should return empty outputs.",
    )
    unwrap_single: bool = Field(
        default=False,
        description="Return a single embedding when the input was a string.",
    )
    credential_env_vars: dict[str, str | None] = Field(
        default_factory=dict,
        description="Environment variables applied during embedding execution.",
    )

    @field_validator("embedding_method")
    @classmethod
    def _validate_embedding_method(cls, value: str) -> str:
        if not value:
            raise ValueError("embedding_method must be a non-empty string")
        if value not in _EMBEDDING_METHODS:
            raise ValueError(f"Unknown embedding method '{value}'")
        return value

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Embed configured text input and return normalized vectors."""
        texts, is_single = self._resolve_texts(state)
        if not texts:
            if self.allow_empty:
                return self._empty_payload(is_single)
            msg = "TextEmbeddingNode requires at least one non-empty text input"
            raise ValueError(msg)

        method = self._resolve_embedding_method(config)
        embedder = resolve_embedding_method(method)

        with _temporary_env_vars(self.credential_env_vars):
            output = embedder(texts)
            if inspect.isawaitable(output):
                output = await output  # type: ignore[assignment]
        try:
            vectors = normalize_embedding_output(output)
        except ValueError as exc:
            raise ValueError(EMBEDDING_PAYLOAD_ERROR) from exc

        payload: dict[str, Any] = {}
        payload[self.output_key] = self._maybe_unwrap(vectors, is_single)

        if self.dense_output_key:
            dense_vectors = require_dense_embeddings(vectors)
            payload[self.dense_output_key] = self._maybe_unwrap(
                dense_vectors, is_single
            )

        if self.text_output_key:
            payload[self.text_output_key] = self._maybe_unwrap(texts, is_single)

        return payload

    def _resolve_texts(self, state: State) -> tuple[list[str], bool]:
        value = self._extract_input_value(state)
        if value is None:
            return [], False
        if isinstance(value, str):
            return self._coerce_string(value)
        if isinstance(value, list):
            return self._coerce_list(value)
        msg = "TextEmbeddingNode requires a string or list of strings"
        raise ValueError(msg)

    def _extract_input_value(self, state: State) -> Any | None:
        if not isinstance(state, Mapping):
            return None  # pragma: no cover - defensive
        if self.input_key in state:
            return state.get(self.input_key)
        inputs = state.get("inputs")
        if isinstance(inputs, Mapping) and self.input_key in inputs:
            return inputs.get(self.input_key)
        return None

    @staticmethod
    def _coerce_string(value: str) -> tuple[list[str], bool]:
        if not value.strip():
            return [], True
        return [value], True

    def _coerce_list(self, value: list[Any]) -> tuple[list[str], bool]:
        if not value:
            return [], False
        return [self._validate_text_item(item) for item in value], False

    @staticmethod
    def _validate_text_item(item: Any) -> str:
        if not isinstance(item, str):
            msg = "TextEmbeddingNode requires a string or list of strings"
            raise ValueError(msg)
        if not item.strip():
            msg = "TextEmbeddingNode requires non-empty text strings"
            raise ValueError(msg)
        return item

    def _resolve_embedding_method(self, config: RunnableConfig) -> str:
        configurable = config.get("configurable", {})
        if isinstance(configurable, Mapping) and self.embedding_method_key:
            override = configurable.get(self.embedding_method_key)
            if isinstance(override, str) and override.strip():
                return override
        return self.embedding_method

    def _empty_payload(self, is_single: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {self.output_key: []}
        if self.dense_output_key:
            payload[self.dense_output_key] = []
        if self.text_output_key:
            payload[self.text_output_key] = [] if not is_single else ""
        return payload

    def _maybe_unwrap(self, value: list[Any], is_single: bool) -> Any:
        if self.unwrap_single and is_single:
            return value[0]
        return value


@registry.register(
    NodeMetadata(
        name="VectorStoreUpsertNode",
        description=(
            "Persist vector records produced by an embedding node into storage."
        ),
        category="conversational_search",
    )
)
class VectorStoreUpsertNode(TaskNode):
    """Node that writes pre-computed vector records into a vector store."""

    source_result_key: str = Field(
        default="chunk_embedding",
        description="Name of the upstream result entry containing embeddings.",
    )
    embeddings_field: str = Field(
        default="chunk_embeddings",
        description="Field in upstream result that stores vector records.",
    )
    embedding_names: list[str] | None = Field(
        default=None,
        description="Subset of embedding keys to persist (defaults to all available).",
    )
    vector_store: BaseVectorStore = Field(
        default_factory=InMemoryVectorStore,
        description="Vector store adapter used for persistence.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Upsert vector records into the configured store."""
        payload = self._resolve_embedding_records(state)
        if not payload:
            msg = "No vector records available to persist"
            raise ValueError(msg)

        selected_names: list[str]
        if self.embedding_names:
            missing = [name for name in self.embedding_names if name not in payload]
            if missing:
                msg = f"Embedding names not found in payload: {missing}"
                raise ValueError(msg)
            selected_names = list(self.embedding_names)
        else:
            selected_names = list(payload.keys())

        records: list[VectorRecord] = []
        for name in selected_names:
            entries = payload.get(name, [])
            if not isinstance(entries, list):
                msg = f"Embedding payload for '{name}' must be a list"
                raise ValueError(msg)
            records.extend(VectorRecord.model_validate(record) for record in entries)

        if not records:
            msg = "No vector records available to persist"
            raise ValueError(msg)

        await self.vector_store.upsert(records)

        return {
            "indexed": len(records),
            "ids": [record.id for record in records],
            "embedding_names": selected_names,
            "namespace": getattr(self.vector_store, "namespace", None),
        }

    def _resolve_embedding_records(
        self,
        state: State,
    ) -> dict[str, list[VectorRecord]]:
        results = state.get("results", {})
        source = results.get(self.source_result_key, {})
        if isinstance(source, dict) and self.embeddings_field in source:
            payload = source[self.embeddings_field]
        else:
            payload = results.get(self.embeddings_field)
        if not payload:
            return {}
        if not isinstance(payload, dict):
            msg = "Embedding payload must be a mapping of names to vector records"
            raise ValueError(msg)
        return payload


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
    embedding_method: str = Field(
        ...,
        description="Embedding method identifier applied to chunk content.",
    )
    batch_size: int | str = Field(default=32, description="Chunk batch size")
    max_retries: int | str = Field(default=2, description="Retry attempts")
    backoff_seconds: float | str = Field(
        default=0.05, description="Base backoff for retry attempts"
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
                        values=vector.values,
                        text=chunk.content,
                        metadata=metadata,
                        sparse_values=vector.sparse_values,
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

    async def _embed(self, texts: list[str]) -> list[EmbeddingVector]:
        embedder = resolve_embedding_method(self.embedding_method)
        output = embedder(texts)
        if inspect.isawaitable(output):
            output = await output
        try:
            return normalize_embedding_output(output)
        except ValueError as exc:
            raise ValueError(EMBEDDING_PAYLOAD_ERROR) from exc

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


EMBEDDING_PAYLOAD_ERROR = (
    "Embedding function must return List[List[float]] or sparse embedding payloads"
)
