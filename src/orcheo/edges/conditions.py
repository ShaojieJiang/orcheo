"""Condition evaluation helpers shared across logic nodes."""

from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any, Literal
from pydantic import BaseModel, Field


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


def _combine_condition_results(
    *,
    conditions: Sequence[Condition],
    combinator: Literal["and", "or"],
    default_left: Any | None = None,
) -> tuple[bool, list[dict[str, Any]]]:
    """Evaluate the supplied conditions returning the aggregate and detail payload."""
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


__all__ = [
    "ComparisonOperator",
    "Condition",
    "evaluate_condition",
    "_combine_condition_results",
    "_normalise_case",
]
