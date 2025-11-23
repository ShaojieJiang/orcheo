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
StreamCallable = Callable[[str, int, float], Any]


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
        description=("Stream grounded responses with retry and backpressure controls."),
        category="conversational_search",
    )
)
class StreamingGeneratorNode(TaskNode):
    """Generate responses as token streams with retry and buffer guards."""

    query_key: str = Field(
        default="query", description="Key within inputs holding the user query"
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
            "You are a streaming responder. Use the provided context to answer the "
            "query and emit partial tokens promptly."
        ),
        description="Instruction prefix prepended to the prompt.",
    )
    max_tokens: int = Field(default=512, gt=0, description="Token cap for generation")
    temperature: float = Field(
        default=0.1, ge=0.0, description="Sampling temperature used by the model"
    )
    max_retries: int = Field(default=1, ge=0, description="Maximum retry attempts")
    backoff_seconds: float = Field(
        default=0.05, ge=0.0, description="Base backoff delay between retries"
    )
    max_buffer_size: int = Field(
        default=64,
        gt=0,
        description="Maximum number of chunks retained before backpressure triggers",
    )
    llm_streamer: StreamCallable | None = Field(
        default=None,
        description=(
            "Callable returning an async iterator or iterable yielding response chunks"
        ),
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Stream a grounded response with retries and buffer enforcement."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "StreamingGeneratorNode requires a non-empty query string"
            raise ValueError(msg)

        context = self._resolve_context(state)
        prompt = self._build_prompt(query.strip(), context)
        tokens = await self._stream_with_retries(prompt)

        response = " ".join(tokens).strip()
        return {
            "response": response,
            "chunks": tokens,
            "chunks_emitted": len(tokens),
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
        return f"{self.system_prompt}\n\nQuestion: {query}\nContext:\n{context_block}"

    async def _stream_with_retries(self, prompt: str) -> list[str]:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return await self._collect_stream(prompt)
            except Exception as exc:  # pragma: no cover - exercised via tests
                last_error = exc
                if attempt == self.max_retries:
                    raise
                delay = self.backoff_seconds * (2**attempt)
                await asyncio.sleep(delay)
        if last_error:
            raise last_error
        return []

    async def _collect_stream(self, prompt: str) -> list[str]:
        streamer = self.llm_streamer or self._default_streamer
        output = streamer(prompt, self.max_tokens, self.temperature)
        tokens: list[str] = []
        async for chunk in self._normalize_stream(output):
            if not chunk:
                continue
            tokens.append(chunk)
            if len(tokens) > self.max_buffer_size:
                msg = "Stream backpressure limit exceeded"
                raise OverflowError(msg)
        return tokens

    async def _normalize_stream(self, output: Any) -> AsyncIterator[str]:
        if inspect.isawaitable(output):
            output = await output
        if hasattr(output, "__aiter__"):
            async for chunk in output:  # type: ignore[misc]
                yield self._coerce_chunk(chunk)
            return
        if isinstance(output, str):
            for chunk in output.split():
                yield chunk
            return
        if isinstance(output, Iterable):
            for chunk in output:
                yield self._coerce_chunk(chunk)
            return
        msg = "Streaming function must return an async iterator, iterable, or string"
        raise TypeError(msg)

    @staticmethod
    def _coerce_chunk(chunk: Any) -> str:
        if chunk is None:
            return ""
        return str(chunk).strip()

    async def _default_streamer(
        self, prompt: str, max_tokens: int, temperature: float
    ) -> AsyncIterator[str]:
        del temperature
        for token in prompt.split()[:max_tokens]:
            yield token
