"""Graph state for the workflow."""

from __future__ import annotations
from typing import Annotated, Any
from langgraph.graph import MessagesState


class State(MessagesState):
    """State for the graph."""

    inputs: dict[str, Any]
    results: Annotated[dict[str, Any], dict_reducer]


def dict_reducer(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Reducer for dictionaries."""
    return {**left, **right}
