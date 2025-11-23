"""Generation node for conversational search pipelines."""

from __future__ import annotations
import asyncio
from collections.abc import Callable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


GenerationCallable = Callable[[str, list[SearchResult]], str | Any]


@registry.register(
    NodeMetadata(
        name="GroundedGeneratorNode",
        description="Generate grounded answers with citations using retrieved context.",
        category="conversational_search",
    )
)
class GroundedGeneratorNode(TaskNode):
    """Compose grounded responses from retrieved context with retries."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    context_result_key: str = Field(
        default="retrieval",
        description="Key within ``state.results`` containing retrieval payloads.",
    )
    context_field: str = Field(
        default="results",
        description="Field name containing the list of context results to cite.",
    )
    max_retries: int = Field(
        default=3,
        ge=1,
        description="Maximum attempts including the initial generation run.",
    )
    base_delay_seconds: float = Field(
        default=0.1,
        ge=0.0,
        description="Initial backoff delay applied between retries.",
    )
    backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        description="Multiplier applied to the delay after each failed attempt.",
    )
    system_prompt: str = Field(
        default=(
            "You are a grounded responder. Use the provided context to answer "
            "concisely and include citations."
        ),
        description="System instruction prepended to generations.",
    )
    generator: GenerationCallable | None = Field(
        default=None,
        description="Optional callable used to produce a response string.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate a grounded answer with retries and citations."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "GroundedGeneratorNode requires a non-empty query string"
            raise ValueError(msg)

        context = self._resolve_context(state)
        if not context:
            msg = "GroundedGeneratorNode requires at least one context result"
            raise ValueError(msg)

        attempts = 0
        delays: list[float] = []
        last_error: Exception | None = None
        while attempts < self.max_retries:
            attempts += 1
            try:
                response_text = await self._generate_response(query.strip(), context)
                citations = self._build_citations(context)
                citation_markers = " ".join(f"[{item['id']}]" for item in citations)
                response = (
                    f"{self.system_prompt} {response_text} {citation_markers}".strip()
                )
                tokens_used = len(response.split())
                return {
                    "response": response,
                    "citations": citations,
                    "tokens_used": tokens_used,
                    "attempts": attempts,
                    "backoff_schedule": delays,
                }
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempts >= self.max_retries:
                    msg = "GroundedGeneratorNode exhausted retries"
                    raise RuntimeError(msg) from exc
                delay = self.base_delay_seconds * (
                    self.backoff_factor ** (attempts - 1)
                )
                delays.append(delay)
                if delay:
                    await asyncio.sleep(delay)

        if last_error:
            raise last_error
        msg = "GroundedGeneratorNode failed without executing generation"
        raise RuntimeError(msg)

    def _resolve_context(self, state: State) -> list[SearchResult]:
        results = state.get("results", {})
        source = results.get(self.context_result_key, {})
        if isinstance(source, dict) and self.context_field in source:
            payload = source[self.context_field]
        else:
            payload = results.get(self.context_field)
        if not payload:
            return []
        if not isinstance(payload, list):
            msg = "context payload must be a list"
            raise ValueError(msg)
        return [SearchResult.model_validate(item) for item in payload]

    async def _generate_response(self, query: str, context: list[SearchResult]) -> str:
        if self.generator is None:
            context_summary = " ".join(entry.text.strip() for entry in context)
            return f"Based on the context, {query}. {context_summary}".strip()

        result = self.generator(query, context)
        if asyncio.iscoroutine(result):
            result = await result
        if not isinstance(result, str):
            msg = "generator must return a string response"
            raise ValueError(msg)
        return result

    def _build_citations(self, context: list[SearchResult]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for index, result in enumerate(context, start=1):
            snippet = result.text.strip()
            citations.append(
                {
                    "id": str(index),
                    "source_id": result.id,
                    "snippet": snippet[:200],
                    "metadata": result.metadata,
                    "sources": result.sources,
                }
            )
        return citations


__all__ = ["GroundedGeneratorNode"]
