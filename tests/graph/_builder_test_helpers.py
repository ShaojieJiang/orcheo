"""Shared helpers for builder tests."""

from __future__ import annotations
from typing import Any


class DummyGraph:
    """Minimal graph stub recording added edges and conditional routes."""

    def __init__(self) -> None:
        self.edges: list[tuple[Any, Any]] = []
        self.conditional_calls: list[dict[str, Any]] = []

    def add_edge(self, source: Any, target: Any) -> None:
        self.edges.append((source, target))

    def add_conditional_edges(self, *args: Any, **kwargs: Any) -> None:
        self.conditional_calls.append({"args": args, "kwargs": kwargs})


class StubDecision:
    """Simple async decision node that yields predetermined outcomes."""

    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = list(outcomes)

    async def __call__(self, state: Any, config: Any) -> Any:  # noqa: ARG002
        return self._outcomes.pop(0)
