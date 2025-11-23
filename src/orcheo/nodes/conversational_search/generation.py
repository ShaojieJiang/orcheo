"""Grounded generation node for conversational search pipelines."""

from __future__ import annotations
import asyncio
import inspect
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


LLMCallable = Callable[[str, int, float], str | Awaitable[str]]
StreamCallable = Callable[[str, int, float], AsyncIterator[str] | Iterable[str]]


def _truncate_snippet(text: str, limit: int = 160) -> str:
    snippet = text.strip().replace("\n", " ")
    if limit <= 0:
        return ""
    if len(snippet) <= limit:
        return snippet

    ellipsis = "…"
    if limit <= len(ellipsis):
        return ellipsis if limit >= len(ellipsis) else snippet[:limit]

    available = limit - len(ellipsis)
    truncated = snippet[:available].rstrip()
    if not truncated:
        return ellipsis
    return f"{truncated}{ellipsis}"


@registry.register(
    NodeMetadata(
        name="GroundedGeneratorNode",
        description="Generate grounded answers with citations and retry semantics.",
        category="conversational_search",
    )
)
class GroundedGeneratorNode(TaskNode):
    """Node that generates grounded responses using retrieved context."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    context_result_key: str = Field(
        default="retriever",
        description="Name of the upstream result entry containing retrieval output.",
    )
    context_field: str = Field(
        default="results",
        description=(
            "Field name under the retrieval result that stores SearchResult items."
        ),
    )
    system_prompt: str = Field(
        default=(
            "You are a grounded answer generator. Use the provided context to answer "
            "the user's query and include citation markers referencing the context "
            "entries."
        ),
        description="Instruction prefix prepended to the prompt.",
    )
    citation_style: Literal["inline", "footnote", "endnote"] = Field(
        default="inline", description="Style hint for formatting citations."
    )
    max_tokens: int = Field(default=512, gt=0, description="Token cap for generation")
    temperature: float = Field(
        default=0.1, ge=0.0, description="Sampling temperature used by the model"
    )
    max_retries: int = Field(default=2, ge=0, description="Maximum retry attempts")
    backoff_seconds: float = Field(
        default=0.1, ge=0.0, description="Base backoff delay between retries"
    )
    llm: LLMCallable | None = Field(
        default=None,
        description=(
            "Optional callable invoked with ``(prompt, max_tokens, temperature)`` to "
            "produce a completion. A deterministic fallback is used when omitted."
        ),
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate a grounded response with citations and retry semantics."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "GroundedGeneratorNode requires a non-empty query string"
            raise ValueError(msg)

        context = self._resolve_context(state)
        if not context:
            msg = "GroundedGeneratorNode requires at least one context document"
            raise ValueError(msg)

        prompt = self._build_prompt(query.strip(), context)
        completion = await self._generate_with_retries(prompt)

        citations = self._build_citations(context)
        response = self._attach_citations(completion, citations)
        tokens_used = self._estimate_tokens(prompt, response)

        return {
            "response": response,
            "citations": citations,
            "tokens_used": tokens_used,
            "citation_style": self.citation_style,
        }

    def _resolve_context(self, state: State) -> list[SearchResult]:
        results = state.get("results", {})
        source = results.get(self.context_result_key, {})
        if isinstance(source, dict) and self.context_field in source:
            entries = source[self.context_field]
        else:
            entries = results.get(self.context_field)
        if not entries:
            return []
        if not isinstance(entries, list):
            msg = "Context payload must be a list of retrieval results"
            raise ValueError(msg)
        return [SearchResult.model_validate(item) for item in entries]

    def _build_prompt(self, query: str, context: list[SearchResult]) -> str:
        context_block = "\n".join(
            f"[{index}] {entry.text}" for index, entry in enumerate(context, start=1)
        )
        return (
            f"{self.system_prompt}\n\n"
            f"Question: {query}\n"
            f"Context:\n{context_block}\n\n"
            f"Cite sources in {self.citation_style} style using the provided "
            "identifiers."
        )

    async def _generate_with_retries(self, prompt: str) -> str:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self._invoke_llm(prompt)
            except Exception as exc:  # pragma: no cover - exercised via tests
                last_error = exc
                if attempt == self.max_retries:
                    raise
                delay = self.backoff_seconds * (2**attempt)
                await asyncio.sleep(delay)
        msg = f"Generation failed after {self.max_retries + 1} attempts"
        raise RuntimeError(msg) from last_error

    async def _invoke_llm(self, prompt: str) -> str:
        llm_callable = self.llm or self._default_llm
        result = llm_callable(prompt, self.max_tokens, self.temperature)
        if inspect.isawaitable(result):
            result = await result
        if not isinstance(result, str) or not result.strip():
            msg = "LLM callable must return a non-empty string"
            raise ValueError(msg)
        return result.strip()

    def _default_llm(self, prompt: str, max_tokens: int, temperature: float) -> str:
        del max_tokens, temperature
        return f"{prompt}\n\nResponse: See cited context for details."

    def _build_citations(self, context: list[SearchResult]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for index, entry in enumerate(context, start=1):
            citations.append(
                {
                    "id": str(index),
                    "source_id": entry.id,
                    "snippet": _truncate_snippet(entry.text),
                    "sources": entry.sources
                    or ([entry.source] if entry.source else []),
                }
            )
        return citations

    def _attach_citations(
        self, completion: str, citations: list[dict[str, Any]]
    ) -> str:
        markers = " ".join(f"[{citation['id']}]" for citation in citations)
        if not markers:
            return completion
        if self.citation_style == "footnote":
            return f"{completion}\n\nFootnotes: {markers}".strip()
        if self.citation_style == "endnote":
            return f"{completion}\n\nEndnotes: {markers}".strip()
        return f"{completion} {markers}".strip()

    @staticmethod
    def _estimate_tokens(prompt: str, completion: str) -> int:
        return len((prompt + completion).split())


@registry.register(
    NodeMetadata(
        name="StreamingGeneratorNode",
        description="Stream grounded answers with backpressure and retry controls.",
        category="conversational_search",
    )
)
class StreamingGeneratorNode(GroundedGeneratorNode):
    """Stream responses while enforcing buffer limits."""

    streaming_llm: StreamCallable | None = Field(
        default=None,
        description=(
            "Callable yielding completion tokens asynchronously. Falls back to a "
            "deterministic iterator when omitted."
        ),
    )
    max_buffer: int = Field(
        default=128,
        gt=0,
        description="Maximum number of tokens buffered before triggering backpressure.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Stream a response while retrying on transient failures."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "StreamingGeneratorNode requires a non-empty query string"
            raise ValueError(msg)

        context = self._resolve_context(state)
        if not context:
            msg = "StreamingGeneratorNode requires at least one context document"
            raise ValueError(msg)

        prompt = self._build_prompt(query.strip(), context)
        segments, attempts = await self._stream_with_retries(prompt)
        response = self._attach_citations(
            "".join(segments), self._build_citations(context)
        )

        return {
            "response": response,
            "segments": segments,
            "attempts": attempts,
            "buffer_size": len(segments),
        }

    async def _stream_with_retries(self, prompt: str) -> tuple[list[str], int]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                segments = await self._consume_stream(prompt)
                return segments, attempt + 1
            except Exception as exc:  # pragma: no cover - retry guard
                last_error = exc
                if attempt == self.max_retries:
                    raise
                delay = self.backoff_seconds * (2**attempt)
                await asyncio.sleep(delay)
        raise RuntimeError("Streaming generation failed") from last_error

    async def _consume_stream(self, prompt: str) -> list[str]:
        generator = self.streaming_llm or self._default_streaming_llm
        stream = generator(prompt, self.max_tokens, self.temperature)
        segments: list[str] = []

        if inspect.isasyncgen(stream) or hasattr(stream, "__aiter__"):
            async for chunk in stream:  # type: ignore[misc]
                segments.append(self._normalize_chunk(chunk))
                if len(segments) > self.max_buffer:
                    raise BufferError("stream buffer exceeded")
        else:
            if not isinstance(stream, Iterable):
                msg = "Streaming LLM must return an iterator of strings"
                raise TypeError(msg)
            for chunk in stream:
                segments.append(self._normalize_chunk(chunk))
                if len(segments) > self.max_buffer:
                    raise BufferError("stream buffer exceeded")
        return segments

    @staticmethod
    def _normalize_chunk(chunk: Any) -> str:
        if not isinstance(chunk, str):
            msg = "Streaming LLM must yield string segments"
            raise TypeError(msg)
        return chunk

    def _default_streaming_llm(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> Iterable[str]:
        del max_tokens, temperature
        for word in prompt.split():
            yield f"{word} "


@registry.register(
    NodeMetadata(
        name="HallucinationGuardNode",
        description="Detect risky responses and route to fallback flows.",
        category="conversational_search",
    )
)
class HallucinationGuardNode(TaskNode):
    """Lightweight guardrail for hallucination-prone responses."""

    source_result_key: str = Field(
        default="grounded_generator", description="Upstream result containing response"
    )
    response_field: str = Field(
        default="response", description="Field name holding the generated response"
    )
    citations_field: str = Field(
        default="citations", description="Field containing citation payloads"
    )
    require_citations: bool = Field(
        default=True,
        description="Whether responses must include citations to be considered safe.",
    )
    banned_keywords: set[str] = Field(
        default_factory=lambda: {"hallucination", "fabricated", "invented"},
        description="Keywords that trigger a guardrail failure when present.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Apply lightweight hallucination checks to a response payload."""
        payload = state.get("results", {}).get(self.source_result_key, {})
        response = (
            payload.get(self.response_field) if isinstance(payload, dict) else None
        )
        citations = (
            payload.get(self.citations_field) if isinstance(payload, dict) else None
        )

        if not isinstance(response, str) or not response.strip():
            msg = "HallucinationGuardNode requires a non-empty response"
            raise ValueError(msg)

        flags: list[str] = []
        normalized = response.lower()
        if self.require_citations:
            has_citations = isinstance(citations, list) and len(citations) > 0
            if not has_citations:
                flags.append("missing_citations")
        for keyword in self.banned_keywords:
            if keyword in normalized:
                flags.append("banned_keyword")

        status = "ok" if not flags else "blocked"
        route = "proceed" if status == "ok" else "fallback"
        return {
            "status": status,
            "route": route,
            "flags": flags,
            "response": response,
            "citations": citations or [],
        }


@registry.register(
    NodeMetadata(
        name="CitationsFormatterNode",
        description="Normalize citation payloads for client rendering.",
        category="conversational_search",
    )
)
class CitationsFormatterNode(TaskNode):
    """Produce structured citation objects with user-friendly fields."""

    source_result_key: str = Field(
        default="grounded_generator", description="Upstream result containing citations"
    )
    citations_field: str = Field(
        default="citations", description="Field holding raw citation payloads"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Normalize citation payloads for downstream rendering."""
        payload = state.get("results", {}).get(self.source_result_key, {})
        citations = (
            payload.get(self.citations_field) if isinstance(payload, dict) else None
        )
        if citations is None:
            return {"citations": []}
        if not isinstance(citations, list):
            msg = "citations payload must be a list"
            raise ValueError(msg)

        formatted = [
            {
                "id": str(index + 1),
                "source_id": entry.get("source_id") or entry.get("id"),
                "snippet": _truncate_snippet(str(entry.get("snippet", "")), limit=120),
                "sources": entry.get("sources") or [],
            }
            for index, entry in enumerate(citations)
        ]
        return {"citations": formatted}
