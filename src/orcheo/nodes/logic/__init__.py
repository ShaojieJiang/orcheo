"""Logic nodes split across focused modules for maintainability."""

from orcheo.nodes.logic.branching import (
    IfElseNode,
    SwitchCase,
    SwitchNode,
    WhileNode,
    _coerce_branch_key,
)
from orcheo.nodes.logic.conditions import (
    ComparisonOperator,
    Condition,
    _combine_condition_results,
    _contains,
    _normalise_case,
    evaluate_condition,
)
from orcheo.nodes.logic.utilities import (
    DelayNode,
    SetVariableNode,
    _build_nested,
)


__all__ = [
    "ComparisonOperator",
    "Condition",
    "SwitchCase",
    "IfElseNode",
    "SwitchNode",
    "WhileNode",
    "SetVariableNode",
    "DelayNode",
    "evaluate_condition",
    "_combine_condition_results",
    "_coerce_branch_key",
    "_contains",
    "_normalise_case",
    "_build_nested",
]
