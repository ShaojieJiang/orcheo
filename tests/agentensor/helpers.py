"""Helper evaluators used by the Agentensor node unit tests."""

from __future__ import annotations
from typing import Any


def simple_result(context: Any) -> dict[str, Any]:
    """Return a dictionary that signals success."""
    return {"value": True, "reason": "ok"}


def numeric_result(context: Any) -> float:
    """Return a numeric score to test the numeric branch."""
    return 0.75


class EvaluateCallable:
    """Evaluator that exposes an ``evaluate`` method."""

    def evaluate(self, context: Any) -> dict[str, Any]:
        return {"value": 0.2, "reason": "evaluate-called"}
