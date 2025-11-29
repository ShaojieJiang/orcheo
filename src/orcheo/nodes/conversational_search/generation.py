"""Grounded generation node for conversational search pipelines."""

from __future__ import annotations
import asyncio
from typing import Any, Literal
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


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
    ai_model: str | None = Field(
        default=None,
        description=(
            "Optional model identifier (e.g., 'gpt-4', 'claude-3-5-sonnet-latest'). "
            "When specified, an agent is created using langchain.agents.create_agent. "
            "A deterministic fallback is used when omitted."
        ),
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate a grounded response with citations and retry semantics.

        If no context is available, generates a response without RAG or citations.
        """
        inputs = state.get("inputs", {})
        query = inputs.get(self.query_key) or inputs.get("message")
        if not isinstance(query, str) or not query.strip():
            msg = "GroundedGeneratorNode requires a non-empty query string"
            raise ValueError(msg)

        context = self._resolve_context(state)

        # Handle non-RAG mode when no context is available
        if not context:
            prompt = self._build_non_rag_prompt(query.strip())
            completion = await self._generate_with_retries(prompt)
            tokens_used = self._estimate_tokens(prompt, completion)
            return {
                "reply": completion,
                "citations": [],
                "tokens_used": tokens_used,
                "citation_style": self.citation_style,
                "mode": "non_rag",
            }

        # RAG mode with context and citations
        prompt = self._build_prompt(query.strip(), context)
        completion = await self._generate_with_retries(prompt)

        citations = self._build_citations(context)
        response = self._attach_citations(completion, citations)
        tokens_used = self._estimate_tokens(prompt, response)

        return {
            "reply": response,
            "citations": citations,
            "tokens_used": tokens_used,
            "citation_style": self.citation_style,
            "mode": "rag",
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

    def _build_non_rag_prompt(self, query: str) -> str:
        """Build a prompt for non-RAG mode without context or citations."""
        return (
            "You are a helpful assistant. Answer the user's question directly "
            "based on your knowledge.\n\n"
            f"Question: {query}\n"
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
        if self.ai_model:
            # Create agent with the specified model
            from langchain_core.runnables import Runnable

            agent: Runnable = create_agent(
                self.ai_model,
                tools=[],
                system_prompt="",
            )
            # Invoke agent with the prompt as a user message
            messages = [{"role": "user", "content": prompt}]
            result = await agent.ainvoke({"messages": messages})  # type: ignore[arg-type]

            # Extract text from the last message
            if isinstance(result, dict) and "messages" in result:
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
                    text = last_message.content
                elif isinstance(last_message, dict):
                    text = last_message.get("content", "")
                else:
                    text = str(last_message)
            else:
                text = str(result)

            if not isinstance(text, str) or not text.strip():
                msg = "Agent must return a non-empty string response"
                raise ValueError(msg)
            return text.strip()
        else:
            # Use default fallback
            return self._default_llm(prompt, self.max_tokens, self.temperature)

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
    ai_model: str | None = Field(
        default=None,
        description=(
            "Optional model identifier (e.g., 'gpt-4', 'claude-3-5-sonnet-latest'). "
            "When specified, an agent is created using langchain.agents.create_agent."
        ),
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
            "reply": completion,
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
        if self.ai_model:
            # Create agent with the specified model
            from langchain_core.runnables import Runnable

            agent: Runnable = create_agent(
                self.ai_model,
                tools=[],
                system_prompt="",
            )
            # Invoke agent with the prompt as a user message
            messages = [{"role": "user", "content": prompt}]
            result = await agent.ainvoke({"messages": messages})  # type: ignore[arg-type]

            # Extract text from the last message
            if isinstance(result, dict) and "messages" in result:
                last_message = result["messages"][-1]
                if hasattr(last_message, "content"):
                    text = last_message.content
                elif isinstance(last_message, dict):
                    text = last_message.get("content", "")
                else:
                    text = str(last_message)
            else:
                text = str(result)

            if not isinstance(text, str) or not text.strip():
                msg = "Agent must return a non-empty string response"
                raise ValueError(msg)
            return text.strip()
        else:
            # Use default fallback
            return self._default_llm(prompt, self.max_tokens, self.temperature)

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
        default="reply", description="Field containing the model response"
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
            "reply": response,
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
