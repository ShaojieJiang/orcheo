"""Utility nodes providing orchestration helpers."""

from __future__ import annotations
import asyncio
from typing import Any
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="Delay",
        description="Pause execution for a configurable duration.",
        category="utility",
    )
)
class DelayNode(TaskNode):
    """Delay the workflow for a specified duration."""

    seconds: float = Field(default=1.0, ge=0.0, le=300.0)

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Sleep for the configured duration and return the delay."""
        await asyncio.sleep(self.seconds)
        return {"delayed_for": self.seconds}


@registry.register(
    NodeMetadata(
        name="Debug",
        description="Log the current state for diagnostics.",
        category="utility",
    )
)
class DebugNode(TaskNode):
    """Return the current state for debugging purposes."""

    message: str | None = None

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Expose the current state for debugging purposes."""
        snapshot = {"inputs": state.get("inputs"), "results": state.get("results")}
        return {"message": self.message, "snapshot": snapshot}


@registry.register(
    NodeMetadata(
        name="SubWorkflow",
        description="Invoke a reusable sub-workflow definition.",
        category="utility",
    )
)
class SubWorkflowNode(TaskNode):
    """Represent a reusable sub-workflow invocation."""

    name: str
    steps: list[str] = Field(default_factory=list)

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Describe the sub-workflow invocation for downstream nodes."""
        return {
            "sub_workflow": self.name,
            "steps": list(self.steps),
            "invoked_at": config.get("run_id") if isinstance(config, dict) else None,
        }


__all__ = ["DebugNode", "DelayNode", "SubWorkflowNode"]
