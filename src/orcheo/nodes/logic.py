"""Logic and utility nodes for orchestrating flows."""

from __future__ import annotations
import asyncio
from collections.abc import Mapping, Sequence
from typing import Any, Literal
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
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
    """Evaluate the supplied operands using the configured comparison.

    Examples:
        Evaluate an equality check without case sensitivity.

        >>> evaluate_condition(
        ...     left="Hello",
        ...     right="hello",
        ...     operator="equals",
        ...     case_sensitive=False,
        ... )
        True

        Check membership within a sequence.

        >>> evaluate_condition(
        ...     left=["alpha", "beta"],
        ...     right="beta",
        ...     operator="contains",
        ... )
        True
    """
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


class Condition(BaseModel):
    """Configuration for evaluating a single comparison."""

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


def _combine_condition_results(
    *,
    conditions: Sequence[Condition],
    combinator: Literal["and", "or"],
    default_left: Any | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Evaluate the supplied conditions returning the aggregate and detail payload.

    Examples:
        Combine multiple conditions into a single outcome.

        >>> summary, evaluations = _combine_condition_results(
        ...     conditions=[
        ...         Condition(left=2, operator="greater_than", right=5),
        ...         Condition(
        ...             left="Ada",
        ...             operator="equals",
        ...             right="ada",
        ...             case_sensitive=False,
        ...         ),
        ...     ],
        ...     combinator="or",
        ... )
        >>> summary
        True
    """
    if not conditions:
        return False, []

    evaluations: list[dict[str, Any]] = []
    results: list[bool] = []
    for index, condition in enumerate(conditions):
        left_operand = condition.left if condition.left is not None else default_left
        outcome = evaluate_condition(
            left=left_operand,
            right=condition.right,
            operator=condition.operator,
            case_sensitive=condition.case_sensitive,
        )
        evaluations.append(
            {
                "index": index,
                "left": left_operand,
                "right": condition.right,
                "operator": condition.operator,
                "case_sensitive": condition.case_sensitive,
                "result": outcome,
            }
        )
        results.append(outcome)

    aggregated = all(results) if combinator == "and" else any(results)
    return aggregated, evaluations


@registry.register(
    NodeMetadata(
        name="IfElseNode",
        description="Branch execution based on a condition",
        category="logic",
    )
)
class IfElseNode(TaskNode):
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

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the evaluated operands and the resulting branch key."""
        outcome, evaluations = _combine_condition_results(
            conditions=self.conditions,
            combinator=self.condition_logic,
        )
        branch = "true" if outcome else "false"
        return {
            "condition": outcome,
            "branch": branch,
            "condition_logic": self.condition_logic,
            "conditions": evaluations,
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
        description="Store variables for downstream nodes",
        category="utility",
    )
)
class SetVariableNode(TaskNode):
    """Persist multiple variables using a dictionary."""

    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of variables to persist",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the assigned variables."""
        payload: dict[str, Any] = {}

        def merge(base: dict[str, Any], incoming: Mapping[str, Any]) -> None:
            for key, value in incoming.items():
                if isinstance(value, Mapping):
                    existing = base.get(key)
                    if isinstance(existing, dict):
                        merge(existing, value)
                    else:
                        base[key] = dict(value)
                else:
                    base[key] = value

        for name, value in self.variables.items():
            if "." in name:
                nested = _build_nested(name, value)
                merge(payload, nested)
            else:
                existing = payload.get(name)
                if isinstance(existing, dict) and isinstance(value, Mapping):
                    merge(existing, value)
                elif isinstance(value, Mapping):
                    payload[name] = dict(value)
                else:
                    payload[name] = value

        return payload


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


__all__ = [
    "ComparisonOperator",
    "Condition",
    "SwitchCase",
    "IfElseNode",
    "SwitchNode",
    "WhileNode",
    "SetVariableNode",
    "DelayNode",
]
