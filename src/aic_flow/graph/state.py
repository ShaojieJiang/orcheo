"""Graph state for the workflow."""

from __future__ import annotations
from typing import Annotated
from langgraph.graph import MessagesState


class State(MessagesState):
    """State for the graph."""

    outputs: Annotated[dict, dict_reducer]


def dict_reducer(left: dict, right: dict) -> dict:
    """Reducer for dictionaries."""
    return {**left, **right}
