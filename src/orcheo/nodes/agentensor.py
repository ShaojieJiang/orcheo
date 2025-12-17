"""Agentensor evaluation/training node placeholder."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.agentensor.prompts import TrainablePrompts
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="AgentensorNode",
        description=(
            "Evaluate or train agent prompts using Agentensor datasets and evaluators."
        ),
        category="agentensor",
    )
)
class AgentensorNode(TaskNode):
    """Node shell for Agentensor evaluation and training flows."""

    mode: Literal["evaluate", "train"] = "evaluate"
    prompts: TrainablePrompts = Field(
        default_factory=dict,
        description="Trainable prompt definitions resolved from runnable configs.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return resolved prompts and selected mode as a placeholder result."""
        resolved_prompts = {
            name: prompt.model_dump(mode="json")
            for name, prompt in self.prompts.items()
        }
        tag_payload: list[str] | None = None
        if isinstance(config, Mapping):
            tags = config.get("tags")
            if isinstance(tags, list):
                tag_payload = [str(tag) for tag in tags]
        return {
            "mode": self.mode,
            "prompts": resolved_prompts,
            "tags": tag_payload or [],
        }


__all__ = ["AgentensorNode"]
