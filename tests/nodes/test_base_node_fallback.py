"""Tests for BaseNode fallback resolution logic."""

from __future__ import annotations
from typing import cast
from orcheo.graph.state import State
from orcheo.nodes.base import BaseNode


def test_fallback_to_results_requires_mapping() -> None:
    state = cast(State, {"results": ["unexpected"]})

    fallback = BaseNode._fallback_to_results(["output", "value"], 0, state)

    assert fallback is None
