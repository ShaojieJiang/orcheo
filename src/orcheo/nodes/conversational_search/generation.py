"""Grounded generation node with citations and retry semantics."""

from __future__ import annotations
import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry
from orcheo.triggers.retry import RetryPolicyConfig


GenerationFunction = Callable[[str, list[SearchResult]], str | Awaitable[str]]


@registry.register(
    NodeMetadata(
        name="GroundedGeneratorNode",
        description="Generate answers grounded in retrieved context with citations.",
        category="conversational_search",
    )
)
class GroundedGeneratorNode(TaskNode):
    """Synthesise answers while emitting citations and retries."""

    query_key: str = Field(
        default="query",
        description="Key within ``state.inputs`` containing the user query.",
    )
    context_result_key: str = Field(
        default="retrieval_results",
        description="Key under ``state.results`` holding retrieval payloads.",
    )
    context_field: str = Field(
        default="results",
        description=(
            "Field that contains ``SearchResult`` entries within the context payload."
        ),
    )
    history_key: str = Field(
        default="history",
        description="Optional conversation history key within ``state.inputs``.",
    )
    system_prompt: str = Field(
        default=(
            "You are a grounded answer generator. Use the provided context to respond"
            " concisely and include citations."
        ),
        description="Instruction prefix injected ahead of user prompts.",
    )
    citation_style: Literal["inline", "footnote", "endnote"] = Field(
        default="inline", description="Presentation style for citation markers."
    )
    generator: GenerationFunction | None = Field(
        default=None,
        description="Custom callable used to synthesise responses.",
    )
    retry_policy: RetryPolicyConfig = Field(
        default_factory=lambda: RetryPolicyConfig(
            max_attempts=3,
            initial_delay_seconds=0.05,
            backoff_factor=2.0,
            max_delay_seconds=0.2,
            jitter_factor=0.0,
        ),
        description="Retry policy applied to generation failures.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate a grounded response from retrieved context."""
        query = state.get("inputs", {}).get(self.query_key)
        if not isinstance(query, str) or not query.strip():
            msg = "GroundedGeneratorNode requires a non-empty query string"
            raise ValueError(msg)

        context = self._resolve_context(state)
        if not context:
            msg = "GroundedGeneratorNode requires at least one context result"
            raise ValueError(msg)

        history = state.get("inputs", {}).get(self.history_key, []) or []
        if not isinstance(history, list):
            msg = "history must be a list of messages"
            raise ValueError(msg)
        prompt = self._build_prompt(query, context, history)

        response = await self._generate_with_retries(prompt, context)
        citations = self._build_citations(context)

        return {
            "response": response,
            "citations": citations,
            "tokens_used": self._token_count(response),
            "prompt": prompt,
        }

    def _resolve_context(self, state: State) -> list[SearchResult]:
        results = state.get("results", {})
        payload = results.get(self.context_result_key) or results.get(
            self.context_field
        )

        if payload is None:
            return []

        if isinstance(payload, dict) and self.context_field in payload:
            entries = payload[self.context_field]
        else:
            entries = payload

        if not isinstance(entries, list):
            msg = "context results must be provided as a list"
            raise ValueError(msg)

        return [SearchResult.model_validate(item) for item in entries]

    def _build_prompt(
        self, query: str, context: list[SearchResult], history: list[Any]
    ) -> str:
        formatted_context = "\n".join(
            f"[{index}] {result.text}" for index, result in enumerate(context, start=1)
        )
        formatted_history = "\n".join(
            str(entry.get("content", entry)) if isinstance(entry, dict) else str(entry)
            for entry in history
        ).strip()

        prompt_sections = [self.system_prompt.strip(), f"Query: {query.strip()}"]
        if formatted_history:
            prompt_sections.append(f"History:\n{formatted_history}")
        prompt_sections.append(f"Context:\n{formatted_context}")

        return "\n\n".join(section for section in prompt_sections if section)

    async def _generate_with_retries(
        self, prompt: str, context: list[SearchResult]
    ) -> str:
        generator = self.generator or self._default_generator
        last_error: Exception | None = None

        for attempt_index in range(self.retry_policy.max_attempts):
            try:
                output = generator(prompt, context)
                if inspect.isawaitable(output):
                    output = await output  # type: ignore[assignment]
                if not isinstance(output, str) or not output.strip():
                    msg = "Generation function must return a non-empty string"
                    raise ValueError(msg)
                return output.strip()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt_index >= self.retry_policy.max_attempts - 1:
                    raise

                delay = self.retry_policy.compute_delay_seconds(
                    attempt_index=attempt_index
                )
                if delay:
                    await asyncio.sleep(delay)

        assert last_error is not None  # for mypy
        raise last_error

    def _default_generator(self, prompt: str, context: list[SearchResult]) -> str:
        _ = prompt  # prompt is kept for parity with custom generators
        inline_markers = " ".join(
            f"[{index}]" if self.citation_style == "inline" else str(index)
            for index in range(1, len(context) + 1)
        ).strip()
        summary = " ".join(result.text for result in context)
        return f"{summary} {inline_markers}".strip()

    def _build_citations(self, context: list[SearchResult]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for index, result in enumerate(context, start=1):
            citations.append(
                {
                    "id": str(index),
                    "source_id": result.id,
                    "snippet": result.text[:160],
                    "sources": result.sources,
                }
            )
        return citations

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())
