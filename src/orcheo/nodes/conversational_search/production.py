"""Production hardening nodes for conversational search pipelines."""

from __future__ import annotations
import asyncio
import hashlib
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.conversation import (
    BaseMemoryStore,
    InMemoryMemoryStore,
    MemoryTurn,
)
from orcheo.nodes.conversational_search.ingestion import (
    DocumentChunk,
    EmbeddingFunction,
    deterministic_embedding_function,
)
from orcheo.nodes.conversational_search.models import SearchResult, VectorRecord
from orcheo.nodes.conversational_search.vector_store import (
    BaseVectorStore,
    InMemoryVectorStore,
)
from orcheo.nodes.registry import NodeMetadata, registry


LLMCallable = Callable[[str, int, float], str | Awaitable[str]]


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
    """Node that upserts chunk embeddings while skipping unchanged payloads."""

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
        if asyncio.iscoroutine(output):
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


@registry.register(
    NodeMetadata(
        name="StreamingGeneratorNode",
        description="Generate responses and stream token chunks with backpressure.",
        category="conversational_search",
    )
)
class StreamingGeneratorNode(TaskNode):
    """Node that streams model output into bounded frames."""

    prompt_key: str = Field(
        default="prompt", description="Key under inputs containing the prompt."
    )
    max_tokens: int = Field(default=256, gt=0, description="Token limit")
    temperature: float = Field(default=0.2, ge=0.0, description="Sampling temp")
    chunk_size: int = Field(
        default=8, gt=0, description="Maximum tokens per emitted frame"
    )
    buffer_limit: int | None = Field(
        default=64,
        gt=0,
        description="Optional backpressure cap on total tokens streamed.",
    )
    max_retries: int = Field(default=1, ge=0)
    backoff_seconds: float = Field(default=0.05, ge=0.0)
    llm: LLMCallable | None = Field(
        default=None,
        description="Callable invoked with ``(prompt, max_tokens, temperature)``.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Stream a generated response into framed chunks with retries."""
        prompt = state.get("inputs", {}).get(self.prompt_key)
        if not isinstance(prompt, str) or not prompt.strip():
            msg = "StreamingGeneratorNode requires a non-empty prompt"
            raise ValueError(msg)

        completion = await self._generate_with_retries(prompt.strip())
        stream, frames, truncated = self._stream_tokens(completion)
        return {
            "response": completion,
            "stream": stream,
            "frames": frames,
            "token_count": len(stream),
            "truncated": truncated,
        }

    async def _generate_with_retries(self, prompt: str) -> str:
        for attempt in range(self.max_retries + 1):
            try:
                return await self._invoke_llm(prompt)
            except Exception as exc:  # pragma: no cover - exercised via tests
                if attempt == self.max_retries:
                    msg = "Streaming generation failed after retries"
                    raise RuntimeError(msg) from exc
                await asyncio.sleep(self.backoff_seconds * (2**attempt))
        msg = "Streaming generation failed after retries"  # pragma: no cover
        raise RuntimeError(msg)  # pragma: no cover

    async def _invoke_llm(self, prompt: str) -> str:
        llm_callable = self.llm or self._default_llm
        output = llm_callable(prompt, self.max_tokens, self.temperature)
        if asyncio.iscoroutine(output):
            output = await output
        if not isinstance(output, str) or not output.strip():
            msg = "LLM callable must return a non-empty string"
            raise ValueError(msg)
        return output.strip()

    def _stream_tokens(
        self, completion: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        tokens = completion.split()
        truncated = False
        if self.buffer_limit and len(tokens) > self.buffer_limit:
            tokens = tokens[: self.buffer_limit]
            truncated = True

        stream: list[dict[str, Any]] = []
        frames: list[dict[str, Any]] = []
        buffer: list[str] = []
        for index, token in enumerate(tokens):
            stream.append({"index": index, "token": token})
            buffer.append(token)
            if len(buffer) == self.chunk_size:
                frames.append(
                    {
                        "index": len(frames),
                        "chunk": " ".join(buffer),
                        "size": len(buffer),
                    }
                )
                buffer = []
        if buffer:
            frames.append(
                {
                    "index": len(frames),
                    "chunk": " ".join(buffer),
                    "size": len(buffer),
                }
            )
        return stream, frames, truncated

    def _default_llm(self, prompt: str, max_tokens: int, temperature: float) -> str:
        del max_tokens, temperature
        return f"{prompt} :: streamed"


@registry.register(
    NodeMetadata(
        name="HallucinationGuardNode",
        description="Validate generator output for citations and completeness.",
        category="conversational_search",
    )
)
class HallucinationGuardNode(TaskNode):
    """Node that blocks responses missing citations or context alignment."""

    generator_result_key: str = Field(
        default="grounded_generator",
        description="Result entry containing model output and citations.",
    )
    response_field: str = Field(
        default="response", description="Field containing the model response"
    )
    citations_field: str = Field(
        default="citations", description="Field containing citations metadata"
    )
    require_markers: bool = Field(
        default=True,
        description="Whether citation markers like [1] must appear in the response.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Validate generator output includes citations and markers."""
        payload = self._resolve_payload(state)
        response = self._extract_response(payload)
        citations = self._extract_citations(payload)

        if not citations:
            return self._block("Missing citations for generated response")

        missing_markers = self._missing_markers(response, citations)
        if missing_markers:
            reason = "Response is missing citation markers for ids: " + ", ".join(
                sorted(missing_markers)
            )
            return self._block(reason)

        if any(not self._has_snippet(citation) for citation in citations):
            return self._block("Citation entries must include snippets")

        return {
            "allowed": True,
            "response": response,
            "citations": citations,
        }

    def _resolve_payload(self, state: State) -> dict[str, Any]:
        payload = state.get("results", {}).get(self.generator_result_key, {})
        if not isinstance(payload, dict):
            msg = "HallucinationGuardNode requires a mapping payload"
            raise ValueError(msg)
        return payload

    def _extract_response(self, payload: dict[str, Any]) -> str:
        response = payload.get(self.response_field)
        if not isinstance(response, str) or not response.strip():
            msg = "Response payload is missing or empty"
            raise ValueError(msg)
        return response.strip()

    def _extract_citations(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        citations = payload.get(self.citations_field)
        if not isinstance(citations, list) or not citations:
            return []
        normalized: list[dict[str, Any]] = []
        for citation in citations:
            if not isinstance(citation, dict):
                msg = "Citations must be dictionaries"
                raise ValueError(msg)
            normalized.append(citation)
        return normalized

    def _missing_markers(
        self, response: str, citations: list[dict[str, Any]]
    ) -> list[str]:
        if not self.require_markers:
            return []
        missing: list[str] = []
        for citation in citations:
            marker = citation.get("id")
            if marker is None:
                continue
            if f"[{marker}]" not in response:
                missing.append(str(marker))
        return missing

    @staticmethod
    def _has_snippet(citation: dict[str, Any]) -> bool:
        snippet = citation.get("snippet") if isinstance(citation, dict) else None
        return bool(snippet)

    def _block(self, reason: str) -> dict[str, Any]:
        return {
            "allowed": False,
            "reason": reason,
            "fallback_response": "Unable to provide an answer with proper grounding.",
        }


@registry.register(
    NodeMetadata(
        name="ReRankerNode",
        description="Apply secondary scoring to retrieval results for better ranking.",
        category="conversational_search",
    )
)
class ReRankerNode(TaskNode):
    """Node that reorders search results using a reranking function."""

    source_result_key: str = Field(
        default="retriever", description="Result entry holding retrieval output"
    )
    results_field: str = Field(
        default="results", description="Field containing SearchResult entries"
    )
    rerank_function: Callable[[SearchResult], float] | None = Field(default=None)
    top_k: int = Field(default=10, gt=0)
    length_penalty: float = Field(
        default=0.0,
        ge=0.0,
        description="Penalty applied per token to discourage long passages.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Rerank retrieval results using a scoring function."""
        entries = self._resolve_results(state)
        reranked: list[SearchResult] = []
        for entry in entries:
            score = self._score(entry)
            reranked.append(
                SearchResult(
                    id=entry.id,
                    score=score,
                    text=entry.text,
                    metadata=entry.metadata,
                    source=entry.source,
                    sources=entry.sources,
                )
            )
        reranked.sort(key=lambda item: item.score, reverse=True)
        return {"results": reranked[: self.top_k]}

    def _resolve_results(self, state: State) -> list[SearchResult]:
        results = state.get("results", {})
        payload = results.get(self.source_result_key, {})
        if isinstance(payload, dict) and self.results_field in payload:
            entries = payload[self.results_field]
        else:
            entries = payload
        if not isinstance(entries, list):
            msg = "ReRankerNode requires a list of retrieval results"
            raise ValueError(msg)
        return [SearchResult.model_validate(item) for item in entries]

    def _score(self, entry: SearchResult) -> float:
        base_score = entry.score
        if self.rerank_function:
            base_score = self.rerank_function(entry)
        length_penalty = self.length_penalty * len(entry.text.split())
        return base_score - length_penalty


@registry.register(
    NodeMetadata(
        name="SourceRouterNode",
        description="Route fused results into per-source buckets with filtering.",
        category="conversational_search",
    )
)
class SourceRouterNode(TaskNode):
    """Partition search results into source-specific groupings."""

    source_result_key: str = Field(
        default="retriever", description="Result entry containing retrieval items"
    )
    results_field: str = Field(default="results")
    min_score: float = Field(
        default=0.0, ge=0.0, description="Minimum score required to retain entries"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Group results into per-source buckets while filtering by score."""
        entries = self._resolve_results(state)
        routed: dict[str, list[SearchResult]] = {}
        for entry in entries:
            source = entry.source or "unknown"
            bucket = routed.setdefault(source, [])
            if entry.score < self.min_score:
                continue
            bucket.append(entry)
        return {"routed": routed}

    def _resolve_results(self, state: State) -> list[SearchResult]:
        results = state.get("results", {})
        payload = results.get(self.source_result_key, {})
        if isinstance(payload, dict) and self.results_field in payload:
            entries = payload[self.results_field]
        else:
            entries = payload
        if not isinstance(entries, list):
            msg = "SourceRouterNode requires a list of retrieval results"
            raise ValueError(msg)
        return [SearchResult.model_validate(item) for item in entries]


@registry.register(
    NodeMetadata(
        name="CitationsFormatterNode",
        description="Format citation metadata into human-readable strings.",
        category="conversational_search",
    )
)
class CitationsFormatterNode(TaskNode):
    """Node that normalizes and formats citation payloads."""

    source_result_key: str = Field(
        default="grounded_generator",
        description="Result entry containing citations to format.",
    )
    citations_field: str = Field(default="citations")
    include_sources: bool = Field(
        default=True, description="Include source identifiers when available"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Format citations into human-readable strings."""
        payload = state.get("results", {}).get(self.source_result_key, {})
        if isinstance(payload, dict) and self.citations_field in payload:
            citations = payload[self.citations_field]
        else:
            citations = payload
        if not isinstance(citations, list):
            msg = "CitationsFormatterNode requires a list of citations"
            raise ValueError(msg)

        formatted: list[str] = []
        normalized: list[dict[str, Any]] = []
        for citation in citations:
            if not isinstance(citation, dict):
                msg = "Citation entries must be mappings"
                raise ValueError(msg)
            citation_id = citation.get("id") or str(len(formatted) + 1)
            snippet = citation.get("snippet", "").strip()
            sources = citation.get("sources") or []
            normalized.append(
                {
                    "id": str(citation_id),
                    "snippet": snippet,
                    "sources": sources,
                }
            )
            source_label = (
                f" sources={','.join(sources)}"
                if sources and self.include_sources
                else ""
            )
            formatted.append(f"[{citation_id}] {snippet}{source_label}".strip())

        return {"formatted": formatted, "citations": normalized}


@registry.register(
    NodeMetadata(
        name="AnswerCachingNode",
        description="Cache answers by query with TTL-based eviction.",
        category="conversational_search",
    )
)
class AnswerCachingNode(TaskNode):
    """Node that caches responses to repeated questions."""

    query_key: str = Field(
        default="query", description="Key within inputs containing the user query"
    )
    source_result_key: str = Field(
        default="grounded_generator",
        description="Result entry containing a new response to cache.",
    )
    response_field: str = Field(default="response")
    ttl_seconds: int | None = Field(default=300, gt=0)
    max_entries: int = Field(default=256, gt=0)

    cache: OrderedDict[str, tuple[str, float | None]] = Field(  # pragma: no mutate
        default_factory=OrderedDict,
        description="In-memory cache mapping query -> (response, expires_at)",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return cached response for repeated queries when available."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "AnswerCachingNode requires a non-empty query"
            raise ValueError(msg)
        normalized_query = query.strip().lower()

        cached = self._get_cached(normalized_query)
        if cached is not None:
            return {"cached": True, "response": cached}

        response = self._resolve_response(state)
        if response:
            self._store(normalized_query, response)
        return {"cached": False, "response": response}

    def _get_cached(self, query: str) -> str | None:
        entry = self.cache.get(query)
        if entry is None:
            return None
        response, expires_at = entry
        if expires_at is not None and expires_at < time.time():
            self.cache.pop(query, None)
            return None
        # refresh LRU order
        self.cache.move_to_end(query)
        return response

    def _resolve_response(self, state: State) -> str | None:
        payload = state.get("results", {}).get(self.source_result_key, {})
        if isinstance(payload, dict):
            response = payload.get(self.response_field)
        else:
            response = None
        if response is None:
            return None
        if not isinstance(response, str) or not response.strip():
            msg = "Response field must be a non-empty string when provided"
            raise ValueError(msg)
        return response.strip()

    def _store(self, query: str, response: str) -> None:
        if len(self.cache) >= self.max_entries:
            self.cache.popitem(last=False)
        expires_at = time.time() + self.ttl_seconds if self.ttl_seconds else None
        self.cache[query] = (response, expires_at)


@registry.register(
    NodeMetadata(
        name="SessionManagementNode",
        description="Manage conversation sessions with capacity controls.",
        category="conversational_search",
    )
)
class SessionManagementNode(TaskNode):
    """Node that persists conversation turns with pruning."""

    session_id_key: str = Field(
        default="session_id", description="Key under inputs containing session id"
    )
    turns_input_key: str = Field(
        default="turns", description="Optional new turns to append"
    )
    max_turns: int | None = Field(
        default=50,
        ge=1,
        description="Maximum turns retained per session when provided",
    )
    memory_store: BaseMemoryStore = Field(
        default_factory=InMemoryMemoryStore,
        description="Backing store used for session persistence",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Persist new turns and return pruned session history."""
        session_id = state.get("inputs", {}).get(self.session_id_key)
        if not isinstance(session_id, str) or not session_id.strip():
            msg = "SessionManagementNode requires a non-empty session id"
            raise ValueError(msg)
        session_id = session_id.strip()

        new_turns = state.get("inputs", {}).get(self.turns_input_key) or []
        turns = [MemoryTurn.model_validate(turn) for turn in new_turns]
        if turns:
            await self.memory_store.batch_append_turns(session_id, turns)

        await self.memory_store.prune(session_id, self.max_turns)
        history = await self.memory_store.load_history(session_id, None)
        return {"history": history, "turn_count": len(history)}


@registry.register(
    NodeMetadata(
        name="MultiHopPlannerNode",
        description="Derive sequential sub-queries for multi-hop answering.",
        category="conversational_search",
    )
)
class MultiHopPlannerNode(TaskNode):
    """Node that decomposes complex questions into ordered hops."""

    query_key: str = Field(
        default="query", description="Key within inputs containing the question"
    )
    max_hops: int = Field(default=3, gt=0)
    delimiter: str = Field(default=" and ", description="Delimiter used for splitting")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Derive sequential hop plan from a composite query."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "MultiHopPlannerNode requires a non-empty query"
            raise ValueError(msg)

        raw_parts = [
            part.strip() for part in query.split(self.delimiter) if part.strip()
        ]
        if not raw_parts:
            raw_parts = [query.strip()]

        hops: list[dict[str, Any]] = []
        for index, part in enumerate(raw_parts[: self.max_hops]):
            hops.append(
                {
                    "id": f"hop-{index + 1}",
                    "query": part,
                    "depends_on": hops[-1]["id"] if hops else None,
                }
            )

        return {"plan": hops, "hop_count": len(hops)}
