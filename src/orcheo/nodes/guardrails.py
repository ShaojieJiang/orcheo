"""Guardrails node that evaluates workflow quality signals."""

from __future__ import annotations
from typing import Any
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="Guardrails",
        description="Evaluate runtime payloads against configured guardrails",
        category="governance",
    )
)
class GuardrailsNode(TaskNode):
    """Node verifying metrics and emitting evaluation results."""

    name: str
    max_latency_ms: int | None = None
    max_tokens: int | None = None
    required_fields: list[str] | None = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Evaluate stored metrics against configured thresholds."""
        result = {
            "latency_ok": True,
            "token_budget_ok": True,
            "missing_fields": [],
        }

        metrics = state.get("results", {}).get("metrics", {})
        if self.max_latency_ms is not None:
            latency = metrics.get("latency_ms")
            if latency is not None and latency > self.max_latency_ms:
                result["latency_ok"] = False
        if self.max_tokens is not None:
            tokens = metrics.get("tokens")
            if tokens is not None and tokens > self.max_tokens:
                result["token_budget_ok"] = False

        if self.required_fields:
            payload = state.get("results", {}).get("payload", {})
            missing = [field for field in self.required_fields if field not in payload]
            result["missing_fields"] = missing

        result["passed"] = (
            result["latency_ok"]
            and result["token_budget_ok"]
            and not result["missing_fields"]
        )
        return result


__all__ = ["GuardrailsNode"]
