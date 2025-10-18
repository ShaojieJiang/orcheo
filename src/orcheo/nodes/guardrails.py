"""Guardrails node to evaluate workflow quality gates."""

from __future__ import annotations
from typing import Any
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="Guardrails",
        description="Evaluate guardrails and emit compliance reports.",
        category="utility",
    )
)
class GuardrailsNode(TaskNode):
    """Guardrails node evaluating dynamic checks."""

    metrics: dict[str, float] = Field(default_factory=dict)
    thresholds: dict[str, float] = Field(default_factory=dict)

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Evaluate metric thresholds and produce compliance results."""
        evaluations: dict[str, bool] = {}
        for metric, value in self.metrics.items():
            threshold = self.thresholds.get(metric)
            evaluations[metric] = True if threshold is None else value <= threshold
        compliant = all(evaluations.values())
        return {
            "evaluations": evaluations,
            "compliant": compliant,
            "metrics": self.metrics,
        }


__all__ = ["GuardrailsNode"]
