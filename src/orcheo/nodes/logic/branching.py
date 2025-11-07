"""Branching logic nodes built on shared condition helpers."""

from __future__ import annotations
from collections.abc import Mapping
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.base import DecisionNode, TaskNode
from orcheo.nodes.logic.conditions import (
    Condition,
    _combine_condition_results,
    _normalise_case,
)
from orcheo.nodes.registry import NodeMetadata, registry


class SwitchCase(BaseModel):
    """Configuration describing an individual switch branch."""

    match: Any | None = Field(
        default=None, description="Value that activates this branch"
    )
    label: str | None = Field(
        default=None, description="Optional label used in the canvas"
    )
    branch_key: str | None = Field(
        default=None,
        description="Identifier emitted when this branch is selected",
    )
    case_sensitive: bool | None = Field(
        default=None,
        description="Override case-sensitivity for this branch",
    )


def _coerce_branch_key(candidate: str | None, fallback: str) -> str:
    """Return a normalised branch identifier."""
    if candidate:
        candidate = candidate.strip()
    if candidate:
        return candidate
    slug = fallback.strip().lower().replace(" ", "_")
    slug = "".join(char for char in slug if char.isalnum() or char in {"_", "-"})
    return slug or fallback


@registry.register(
    NodeMetadata(
        name="IfElseNode",
        description="Branch execution based on a condition",
        category="logic",
    )
)
class IfElseNode(DecisionNode):
    """Evaluate a boolean expression and emit the chosen branch."""

    conditions: list[Condition] = Field(
        default_factory=lambda: [Condition(left=True, operator="is_truthy")],
        min_length=1,
        description="Collection of conditions that control branching",
    )
    condition_logic: Literal["and", "or"] = Field(
        default="and",
        description="Combine conditions using logical AND/OR semantics",
    )

    async def run(self, state: State, config: RunnableConfig) -> str:
        """Return the evaluated branch key."""
        outcome, evaluations = _combine_condition_results(
            conditions=self.conditions,
            combinator=self.condition_logic,
        )
        branch = "true" if outcome else "false"
        return branch


@registry.register(
    NodeMetadata(
        name="SwitchNode",
        description="Resolve a case key for downstream branching",
        category="logic",
    )
)
class SwitchNode(TaskNode):
    """Map an input value to a branch identifier."""

    value: Any = Field(description="Value to inspect for routing decisions")
    case_sensitive: bool = Field(
        default=True,
        description="Preserve case when deriving branch keys",
    )
    default_branch_key: str = Field(
        default="default",
        description="Branch identifier returned when no cases match",
    )
    cases: list[SwitchCase] = Field(
        default_factory=list,
        min_length=1,
        description="Collection of matchable branches",
    )

    def _resolve_case(
        self, case: SwitchCase, *, index: int, normalised_value: Any
    ) -> tuple[str, bool, dict[str, Any]]:
        case_sensitive = (
            case.case_sensitive
            if case.case_sensitive is not None
            else self.case_sensitive
        )
        branch_key = _coerce_branch_key(
            case.branch_key,
            fallback=f"case_{index + 1}",
        )
        expected = _normalise_case(
            case.match,
            case_sensitive=case_sensitive,
        )
        is_match = normalised_value == expected
        payload = {
            "branch": branch_key,
            "label": case.label,
            "match": case.match,
            "case_sensitive": case_sensitive,
            "result": is_match,
        }
        return branch_key, is_match, payload

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the raw value and a normalised case key."""
        raw_value = self.value
        processed = _normalise_case(raw_value, case_sensitive=self.case_sensitive)
        branch_key = self.default_branch_key
        evaluations: list[dict[str, Any]] = []

        for index, case in enumerate(self.cases):
            candidate_branch, is_match, payload = self._resolve_case(
                case,
                index=index,
                normalised_value=processed,
            )
            evaluations.append(payload)
            if is_match and branch_key == self.default_branch_key:
                branch_key = candidate_branch

        return {
            "value": raw_value,
            "processed": processed,
            "branch": branch_key,
            "case_sensitive": self.case_sensitive,
            "default_branch": self.default_branch_key,
            "cases": evaluations,
        }


@registry.register(
    NodeMetadata(
        name="WhileNode",
        description="Emit a continue signal while the condition holds",
        category="logic",
    )
)
class WhileNode(TaskNode):
    """Evaluate a condition and loop until it fails or a limit is reached."""

    conditions: list[Condition] = Field(
        default_factory=lambda: [Condition(operator="less_than")],
        min_length=1,
        description="Collection of conditions that control continuation",
    )
    condition_logic: Literal["and", "or"] = Field(
        default="and",
        description="Combine conditions using logical AND/OR semantics",
    )
    max_iterations: int | None = Field(
        default=None,
        ge=1,
        description="Optional guard to stop after this many iterations",
    )

    def _previous_iteration(self, state: State) -> int:
        """Return the iteration count persisted in the workflow state."""
        results = state.get("results")
        if isinstance(results, Mapping):
            node_state = results.get(self.name)
            if isinstance(node_state, Mapping):
                iteration = node_state.get("iteration")
                if isinstance(iteration, int) and iteration >= 0:
                    return iteration
        return 0

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return loop metadata and whether execution should continue."""
        previous_iteration = self._previous_iteration(state)
        outcome, evaluations = _combine_condition_results(
            conditions=self.conditions,
            combinator=self.condition_logic,
            default_left=previous_iteration,
        )
        should_continue = outcome
        limit_reached = False

        if (
            self.max_iterations is not None
            and previous_iteration >= self.max_iterations
        ):
            should_continue = False
            limit_reached = True

        iteration = previous_iteration
        if should_continue:
            iteration += 1

        branch = "continue" if should_continue else "exit"
        return {
            "should_continue": should_continue,
            "iteration": iteration,
            "limit_reached": limit_reached,
            "branch": branch,
            "condition_logic": self.condition_logic,
            "conditions": evaluations,
            "max_iterations": self.max_iterations,
        }


__all__ = [
    "SwitchCase",
    "IfElseNode",
    "SwitchNode",
    "WhileNode",
]
