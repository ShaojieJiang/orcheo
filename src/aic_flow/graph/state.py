"""Graph state for the workflow."""

from __future__ import annotations
from typing import Annotated
from typing_extensions import TypedDict
from .output import add_outputs


class State(TypedDict):
    """State for the graph."""

    outputs: Annotated[dict, add_outputs]
