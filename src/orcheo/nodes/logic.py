"""Logic and utility nodes for orchestrating flows."""

from __future__ import annotations
import asyncio
from collections.abc import Mapping, Sequence
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


ComparisonOperator = Literal[
    "equals",
    "not_equals",
    "greater_than",
    "greater_than_or_equal",
    "less_than",
    "less_than_or_equal",
    "contains",
    "not_contains",
    "in",
    "not_in",
    "is_truthy",
    "is_falsy",
]


def _normalise_case(value: Any, *, case_sensitive: bool) -> Any:
    """Return a value adjusted for case-insensitive comparisons."""
    if case_sensitive or not isinstance(value, str):
        return value
    return value.casefold()


def _contains(container: Any, member: Any, expect: bool) -> bool:
    """Return whether the container includes the supplied member."""
    if isinstance(container, Mapping):
        result = member in container
    elif isinstance(container, str | bytes):
        member_str = str(member)
        result = member_str in container
    elif isinstance(container, Sequence) and not isinstance(container, str | bytes):
        result = member in container
    else:
        msg = "Contains operator expects a sequence or mapping container"
        raise ValueError(msg)

    return result if expect else not result


def evaluate_condition(
    *,
    left: Any | None,
    right: Any | None,
    operator: ComparisonOperator,
    case_sensitive: bool = True,
) -> bool:
    """Evaluate the supplied operands using the configured comparison."""
    left_value = _normalise_case(left, case_sensitive=case_sensitive)
    right_value = _normalise_case(right, case_sensitive=case_sensitive)

    direct_ops: dict[ComparisonOperator, Any] = {
        "equals": lambda: left_value == right_value,
        "not_equals": lambda: left_value != right_value,
        "greater_than": lambda: left_value > right_value,  # type: ignore[operator]
        "greater_than_or_equal": lambda: left_value >= right_value,  # type: ignore[operator]
        "less_than": lambda: left_value < right_value,  # type: ignore[operator]
        "less_than_or_equal": lambda: left_value <= right_value,  # type: ignore[operator]
        "is_truthy": lambda: bool(left_value),
        "is_falsy": lambda: not bool(left_value),
    }

    if operator in direct_ops:
        return direct_ops[operator]()

    if operator == "contains":
        return _contains(left_value, right_value, expect=True)

    if operator == "not_contains":
        return _contains(left_value, right_value, expect=False)

    if operator == "in":
        return _contains(right_value, left_value, expect=True)

    if operator == "not_in":
        return _contains(right_value, left_value, expect=False)

    msg = f"Unsupported operator: {operator}"
    raise ValueError(msg)


@registry.register(
    NodeMetadata(
        name="IfElseNode",
        description="Branch execution based on a condition",
        category="logic",
    )
)
class IfElseNode(TaskNode):
    """Evaluate a boolean expression and emit the chosen branch."""

    left: Any | None = Field(default=None, description="Left-hand operand")
    operator: ComparisonOperator = Field(
        default="equals", description="Comparison operator to evaluate"
    )
    right: Any | None = Field(
        default=None, description="Right-hand operand (if required)"
    )
    case_sensitive: bool = Field(
        default=True,
        description="Apply case-sensitive comparison for string operands",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the evaluated operands and the resulting branch key."""
        outcome = evaluate_condition(
            left=self.left,
            right=self.right,
            operator=self.operator,
            case_sensitive=self.case_sensitive,
        )
        branch = "true" if outcome else "false"
        return {
            "condition": outcome,
            "branch": branch,
            "left": self.left,
            "right": self.right,
            "operator": self.operator,
            "case_sensitive": self.case_sensitive,
        }


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

    @staticmethod
    def _format_case(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the raw value and a normalised case key."""
        raw_value = self.value
        processed = raw_value
        if isinstance(raw_value, str) and not self.case_sensitive:
            processed = raw_value.casefold()

        branch_key = self._format_case(processed)
        return {
            "value": raw_value,
            "processed": processed,
            "case": branch_key,
            "case_sensitive": self.case_sensitive,
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

    left: Any | None = Field(default=None, description="Left-hand operand")
    operator: ComparisonOperator = Field(
        default="less_than",
        description="Comparison operator used to decide whether to continue",
    )
    right: Any | None = Field(
        default=None, description="Right-hand operand (if required)"
    )
    case_sensitive: bool = Field(
        default=True,
        description="Apply case-sensitive comparison for string operands",
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
        comparator_left = self.left if self.left is not None else previous_iteration
        should_continue = evaluate_condition(
            left=comparator_left,
            right=self.right,
            operator=self.operator,
            case_sensitive=self.case_sensitive,
        )
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

        return {
            "should_continue": should_continue,
            "iteration": iteration,
            "limit_reached": limit_reached,
            "left": comparator_left,
            "right": self.right,
            "operator": self.operator,
            "case_sensitive": self.case_sensitive,
            "max_iterations": self.max_iterations,
        }


def _build_nested(path: str, value: Any) -> dict[str, Any]:
    """Construct a nested dictionary from a dotted path."""
    if not path:
        msg = "target_path must be a non-empty string"
        raise ValueError(msg)

    segments = [segment.strip() for segment in path.split(".") if segment.strip()]
    if not segments:
        msg = "target_path must contain at least one segment"
        raise ValueError(msg)

    root: dict[str, Any] = {}
    cursor = root
    for segment in segments[:-1]:
        cursor = cursor.setdefault(segment, {})
    cursor[segments[-1]] = value
    return root


@registry.register(
    NodeMetadata(
        name="SetVariableNode",
        description="Store a value for downstream nodes",
        category="utility",
    )
)
class SetVariableNode(TaskNode):
    """Persist a value using dotted path semantics."""

    target_path: str = Field(description="Path to store the provided value")
    value: Any = Field(description="Value to persist")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the assigned value along with a nested representation."""
        nested = _build_nested(self.target_path, self.value)
        return {
            "path": self.target_path,
            "value": self.value,
            "assigned": nested,
        }


@registry.register(
    NodeMetadata(
        name="DelayNode",
        description="Pause execution for a fixed duration",
        category="utility",
    )
)
class DelayNode(TaskNode):
    """Introduce an asynchronous delay within the workflow."""

    duration_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Duration of the pause expressed in seconds",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Sleep for the requested duration and return timing metadata."""
        await asyncio.sleep(self.duration_seconds)
        return {
            "duration_seconds": self.duration_seconds,
        }


@registry.register(
    NodeMetadata(
        name="StickyNoteNode",
        description="Annotate the workflow with contextual information",
        category="utility",
    )
)
class StickyNoteNode(TaskNode):
    """A no-op node that carries human readable context."""

    title: str = Field(default="Note", description="Sticky note title")
    body: str = Field(default="", description="Sticky note contents")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the note payload so it is captured in execution history."""
        return {"title": self.title, "body": self.body}


__all__ = [
    "ComparisonOperator",
    "IfElseNode",
    "SwitchNode",
    "WhileNode",
    "SetVariableNode",
    "DelayNode",
    "StickyNoteNode",
]
