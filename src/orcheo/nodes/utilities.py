"""Utility nodes providing orchestration helpers."""

from __future__ import annotations
from dataclasses import field
from typing import Any
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="JavaScriptCode",
        description="Execute JavaScript snippets in the sandbox runtime",
        category="utility",
    )
)
class JavaScriptCodeNode(TaskNode):
    """Node that forwards JavaScript code for execution."""

    name: str
    source: str
    exports: list[str] = field(default_factory=list)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the JavaScript execution payload."""
        return {
            "language": "javascript",
            "source": self.source,
            "exports": self.exports,
        }


@registry.register(
    NodeMetadata(
        name="Delay",
        description="Pause workflow execution for a fixed interval",
        category="utility",
    )
)
class DelayNode(TaskNode):
    """Node representing a temporal delay."""

    name: str
    seconds: float

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the delay duration."""
        return {"seconds": max(0.0, float(self.seconds))}


@registry.register(
    NodeMetadata(
        name="Debug",
        description="Emit debugging information into run history",
        category="utility",
    )
)
class DebugNode(TaskNode):
    """Node for observing state during execution."""

    name: str
    message: str | None = None
    sample_path: str | None = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Capture debug metadata for the execution history."""
        payload: dict[str, Any] = {"message": self.message}
        if self.sample_path:
            try:
                payload["sample"] = state
                current: Any = state
                for segment in self.sample_path.split("."):
                    if isinstance(current, dict):
                        current = current[segment]
                    else:
                        raise KeyError(segment)
                payload["sample"] = current
            except KeyError:
                payload["sample"] = None
        return payload


@registry.register(
    NodeMetadata(
        name="SubWorkflow",
        description="Invoke a reusable sub-workflow with provided inputs",
        category="utility",
    )
)
class SubWorkflowNode(TaskNode):
    """Node that dispatches another workflow version."""

    name: str
    workflow_id: str
    version: int | None = None
    inputs: dict[str, Any] = field(default_factory=dict)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Describe the sub-workflow invocation."""
        return {
            "workflow_id": self.workflow_id,
            "version": self.version,
            "inputs": self.inputs,
        }


__all__ = [
    "DebugNode",
    "DelayNode",
    "JavaScriptCodeNode",
    "SubWorkflowNode",
]
