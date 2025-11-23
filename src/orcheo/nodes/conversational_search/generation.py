"""Grounded generation node for conversational search graphs."""

from __future__ import annotations
import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


ResponseGenerator = Callable[[str, list[SearchResult]], str | Awaitable[str]]


@registry.register(
    NodeMetadata(
        name="GroundedGeneratorNode",
        description=(
            "Generate grounded responses that cite retrieved context with retry"
            " semantics."
        ),
        category="conversational_search",
    )
)
class GroundedGeneratorNode(TaskNode):
    """Synthesize responses using retrieved context and emit citations."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    context_result_key: str = Field(
        default="retrieval_results",
        description=(
            "Key in ``state.results`` (or inputs) that stores retrieval payloads."
        ),
    )
    context_field: str = Field(
        default="results",
        description=(
            "Optional nested field containing context entries within the source"
            " payload."
        ),
    )
    citation_style: Literal["inline", "footnote", "endnote"] = Field(
        default="inline", description="Formatting hint for downstream renderers."
    )
    max_tokens: int = Field(default=1024, gt=0, description="Maximum response tokens.")
    max_retries: int = Field(
        default=2, ge=0, description="Number of retry attempts on generation failure."
    )
    backoff_seconds: float = Field(
        default=0.05,
        ge=0.0,
        description="Initial backoff delay applied between retries.",
    )
    generator: ResponseGenerator | None = Field(
        default=None,
        description="Optional custom generator callable for producing responses.",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate a grounded response with citations from retrieved context."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "GroundedGeneratorNode requires a non-empty query string"
            raise ValueError(msg)

        context = self._resolve_context(state)
        if not context:
            msg = "GroundedGeneratorNode requires at least one context item"
            raise ValueError(msg)

        response = await self._generate_with_retries(query.strip(), context)
        citations = self._build_citations(context)

        return {
            "response": response,
            "citations": citations,
            "tokens_used": self._token_count(response),
            "context_items": len(context),
            "citation_style": self.citation_style,
        }

    async def _generate_with_retries(
        self, query: str, context: list[SearchResult]
    ) -> str:
        attempts = 0
        last_error: Exception | None = None
        while attempts <= self.max_retries:
            try:
                return await self._invoke_generator(query, context)
            except Exception as exc:  # pragma: no cover - exercised via retries
                last_error = exc
                if attempts >= self.max_retries:
                    raise
                delay = self.backoff_seconds * (2**attempts)
                if delay:
                    await asyncio.sleep(delay)
                attempts += 1
        if last_error is not None:
            raise last_error
        raise RuntimeError("GroundedGeneratorNode failed to generate a response")

    async def _invoke_generator(self, query: str, context: list[SearchResult]) -> str:
        generator = self.generator or self._default_generate
        output = generator(query, context)
        if inspect.isawaitable(output):
            output = await output  # type: ignore[assignment]
        if not isinstance(output, str) or not output.strip():
            msg = "Generator callable must return a non-empty string"
            raise ValueError(msg)
        return output.strip()

    def _resolve_context(self, state: State) -> list[SearchResult]:
        source = state.get("results", {}).get(self.context_result_key)
        if source is None:
            source = state.get("inputs", {}).get(self.context_result_key)
        if source is None:
            return []

        if isinstance(source, dict) and self.context_field in source:
            entries = source[self.context_field]
        else:
            entries = source

        if not isinstance(entries, list):
            msg = (
                "Context for GroundedGeneratorNode must be a list of SearchResult"
                " payloads"
            )
            raise ValueError(msg)

        return [SearchResult.model_validate(item) for item in entries]

    @staticmethod
    def _build_citations(context: list[SearchResult]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for index, result in enumerate(context, start=1):
            citations.append(
                {
                    "id": str(index),
                    "source_id": result.id,
                    "snippet": result.text[:200],
                    "metadata": result.metadata,
                }
            )
        return citations

    def _default_generate(self, query: str, context: list[SearchResult]) -> str:
        snippets = []
        for index, result in enumerate(context, start=1):
            text = result.text.strip()
            if not text:
                continue
            snippets.append(f"{text} [{index}]")
        if not snippets:
            msg = "Context items do not contain usable text for generation"
            raise ValueError(msg)
        summary = " ".join(snippets)
        prefix = f"Answer to '{query}': "
        trimmed = (prefix + summary).split()
        return " ".join(trimmed[: self.max_tokens])

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())
