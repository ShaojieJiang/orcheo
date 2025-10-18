"""Logic and utility nodes for workflow orchestration."""

from __future__ import annotations
import asyncio
import logging
from collections.abc import Iterable
from typing import Any
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field, field_validator
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


_logger = logging.getLogger(__name__)


def _resolve_path(state: State, path: Iterable[str]) -> Any:
    value: Any = state["results"]
    for part in path:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = getattr(value, part, None)
    return value


@registry.register(
    NodeMetadata(
        name="SetVariable",
        description="Set a variable on the workflow state.",
        category="logic",
    )
)
class SetVariable(TaskNode):
    """Assign a value to the workflow results under the node name."""

    value: Any = None

    async def run(self, state: State, config: RunnableConfig) -> Any:
        """Return the configured value without modification."""
        return self.value


@registry.register(
    NodeMetadata(
        name="MergeDictionaries",
        description="Merge multiple dictionaries from the state into one.",
        category="logic",
    )
)
class MergeDictionaries(TaskNode):
    """Merge dictionaries referenced by result keys."""

    sources: list[str] = Field(default_factory=list)

    @field_validator("sources", mode="after")
    @classmethod
    def _dedupe_sources(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for item in value:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Merge the configured sources from workflow results into one payload."""
        merged: dict[str, Any] = {}
        for source in self.sources:
            payload = state["results"].get(source, {})
            if not isinstance(payload, dict):
                msg = f"Source '{source}' is not a dictionary"
                raise ValueError(msg)
            merged.update(payload)
        return merged


@registry.register(
    NodeMetadata(
        name="IfElse",
        description="Route execution based on a boolean condition.",
        category="logic",
    )
)
class IfElse(TaskNode):
    """Return one of two payloads based on a condition."""

    condition: bool = False
    true_payload: Any = Field(default_factory=lambda: {})
    false_payload: Any = Field(default_factory=lambda: {})

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the true or false payload based on the configured condition."""
        return self.true_payload if self.condition else self.false_payload


@registry.register(
    NodeMetadata(
        name="Switch",
        description="Switch between payloads based on a key value.",
        category="logic",
    )
)
class Switch(TaskNode):
    """Return the payload associated with the matching case value."""

    value: Any
    cases: dict[str, Any] = Field(default_factory=dict)
    default: Any = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the matching case payload or the default value."""
        key = str(self.value)
        if key in self.cases:
            return self.cases[key]
        return self.default


@registry.register(
    NodeMetadata(
        name="Delay",
        description="Delay execution for the configured number of seconds.",
        category="utility",
    )
)
class Delay(TaskNode):
    """Delay execution without blocking the event loop."""

    seconds: float = Field(default=1.0, ge=0.0)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Await the requested duration then return it for logging."""
        if self.seconds:
            await asyncio.sleep(self.seconds)
        return {"delayed": self.seconds}


@registry.register(
    NodeMetadata(
        name="Debug",
        description="Log the current state for debugging purposes.",
        category="utility",
    )
)
class Debug(TaskNode):
    """Log messages and return the inspected payload."""

    message: str = ""
    include_results: bool = False

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Log the debug message and optionally include current results."""
        payload: dict[str, Any] = {"message": self.message}
        if self.include_results:
            payload["results"] = state["results"].copy()
        _logger.debug("Debug node %s: %s", self.name, payload)
        return payload


@registry.register(
    NodeMetadata(
        name="SubWorkflow",
        description="Execute a nested sequence of task nodes.",
        category="workflow",
    )
)
class SubWorkflow(TaskNode):
    """Execute nested task nodes in sequence merging their results."""

    steps: list[TaskNode] = Field(default_factory=list)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute each step and merge their `results` into a single payload."""
        combined: dict[str, Any] = {}
        for step in self.steps:
            result = await step(state, config)
            step_results = result.get("results", {})
            combined.update(step_results)
            state["results"].update(step_results)
        return combined


class GuardrailRule(BaseModel):
    """Declarative rule evaluated by the guardrails node."""

    name: str
    path: list[str] = Field(default_factory=list)
    required: bool = False
    max_length: int | None = None
    allowed_values: list[Any] | None = None

    def evaluate(self, state: State) -> tuple[bool, str | None]:
        """Evaluate the rule and return the status with optional message."""
        value = _resolve_path(state, self.path)
        if self.required and value in {None, "", []}:
            return False, f"{self.name} is required"
        if value is None:
            return True, None
        if self.max_length is not None and isinstance(value, str | list | tuple):
            if len(value) > self.max_length:
                return False, f"{self.name} exceeds maximum length"
        if self.allowed_values is not None and value not in self.allowed_values:
            return False, f"{self.name} has disallowed value {value!r}"
        return True, None


@registry.register(
    NodeMetadata(
        name="Guardrails",
        description="Validate results against declarative guardrail rules.",
        category="utility",
    )
)
class Guardrails(TaskNode):
    """Validate workflow state and surface violations as structured output."""

    rules: list[GuardrailRule] = Field(default_factory=list)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Evaluate each guardrail rule and raise if any violations occur."""
        violations: list[str] = []
        for rule in self.rules:
            passed, failure = rule.evaluate(state)
            if not passed and failure:
                violations.append(failure)
        if violations:
            raise ValueError(
                f"Guardrails failed for node {self.name}: {'; '.join(violations)}"
            )
        return {"status": "passed"}


__all__ = [
    "SetVariable",
    "MergeDictionaries",
    "IfElse",
    "Switch",
    "Delay",
    "Debug",
    "SubWorkflow",
    "Guardrails",
    "GuardrailRule",
]
