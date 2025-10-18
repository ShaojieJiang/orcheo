"""AI and LLM nodes with prompt management and latency guardrails."""

from __future__ import annotations
import asyncio
import math
import textwrap
import time
from typing import Any
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import AINode, TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


def _extract_user_prompt(state: State) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, dict):
        return str(last.get("content", ""))
    return str(last)


class LatencyGuardMixin:
    """Mixin that enforces latency guardrails for async operations."""

    max_latency_seconds: float = Field(default=5.0, ge=0.0)

    async def _guard_latency(self, coro: Any) -> tuple[Any, float]:
        start = time.perf_counter()
        result = await coro
        duration = time.perf_counter() - start
        if duration > self.max_latency_seconds:
            message = (
                "Generation exceeded latency guard of "
                f"{self.max_latency_seconds} seconds"
            )
            raise TimeoutError(message)
        return result, duration


@registry.register(
    NodeMetadata(
        name="OpenAIChat",
        description="Simulate an OpenAI chat completion with guardrails.",
        category="ai",
    )
)
class OpenAIChatNode(LatencyGuardMixin, AINode):
    """Simplified OpenAI chat node for offline tests."""

    model: str = "gpt-4o-mini"
    system_prompt: str | None = None

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Generate a simulated OpenAI response respecting latency guardrails."""
        prompt = _extract_user_prompt(state)
        content = textwrap.shorten(prompt, width=200) or "Hello from OpenAI"

        async def _generate() -> str:
            await asyncio.sleep(0)
            prefix = f"[OpenAI {self.model}]"
            if self.system_prompt:
                prefix += f" {self.system_prompt.strip()}"
            return f"{prefix}: {content}"

        message, latency = await self._guard_latency(_generate())
        return {
            "messages": [{"role": "assistant", "content": message}],
            "model": self.model,
            "latency": latency,
        }


@registry.register(
    NodeMetadata(
        name="AnthropicChat",
        description="Simulate an Anthropic Claude response.",
        category="ai",
    )
)
class AnthropicChatNode(LatencyGuardMixin, AINode):
    """Anthropic chat node with deterministic output."""

    model: str = "claude-3-haiku"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Return a deterministic Anthropic-style response."""
        prompt = _extract_user_prompt(state)

        async def _generate() -> str:
            await asyncio.sleep(0)
            return f"[{self.model}] Insight: {prompt[::-1]}"

        message, latency = await self._guard_latency(_generate())
        return {
            "messages": [{"role": "assistant", "content": message}],
            "model": self.model,
            "latency": latency,
        }


@registry.register(
    NodeMetadata(
        name="CustomAgent",
        description="Run a scripted agent with pseudo tool execution.",
        category="ai",
    )
)
class CustomAgentNode(LatencyGuardMixin, AINode):
    """Agent that applies scripted tool instructions."""

    tools: list[str] = Field(default_factory=list)
    instructions: str = ""

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Apply pseudo tool logic to craft an agent reply."""
        prompt = _extract_user_prompt(state)

        async def _generate() -> str:
            await asyncio.sleep(0)
            applied_tools = ", ".join(self.tools) or "no tools"
            response = (
                f"Agent processed '{prompt}' using {applied_tools}. {self.instructions}"
            )
            return response.strip()

        message, latency = await self._guard_latency(_generate())
        return {
            "messages": [{"role": "assistant", "content": message}],
            "latency": latency,
        }


@registry.register(
    NodeMetadata(
        name="TextProcessing",
        description="Perform prompt-aware text processing routines.",
        category="utility",
    )
)
class TextProcessingNode(TaskNode):
    """Perform deterministic text processing for prompts."""

    operation: str = Field(pattern=r"^(word_count|summary|sentiment)$")

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Apply deterministic text processing operations to prompts."""
        prompt = _extract_user_prompt(state)
        if self.operation == "word_count":
            words = [token for token in prompt.split() if token.strip()]
            return {"word_count": len(words)}
        if self.operation == "summary":
            summary = textwrap.shorten(prompt, width=80) or "No content"
            return {"summary": summary}
        if self.operation == "sentiment":
            lowered = prompt.lower()
            score = lowered.count("good") - lowered.count("bad")
            normalized = math.tanh(score)
            return {"sentiment_score": normalized}
        raise ValueError("Unsupported text processing operation")


__all__ = [
    "AnthropicChatNode",
    "CustomAgentNode",
    "OpenAIChatNode",
    "TextProcessingNode",
]
