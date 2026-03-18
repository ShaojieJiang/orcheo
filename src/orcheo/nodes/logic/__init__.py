"""Logic nodes split across focused modules for maintainability.

DEPRECATION NOTICE:
The branching logic (IfElseNode, SwitchNode, WhileNode) has been moved to the
edge system at orcheo.edges.branching. These are now edges
(IfElseEdge, SwitchEdge, WhileEdge) rather than nodes, as they handle routing
decisions rather than data transformations.

Please update your imports:
- from orcheo.nodes.logic import IfElseNode → from orcheo.edges import IfElseEdge
- from orcheo.nodes.logic import SwitchNode → from orcheo.edges import SwitchEdge
- from orcheo.nodes.logic import WhileNode → from orcheo.edges import WhileEdge

Legacy aliases (IfElse, Switch, While) remain available for backward
compatibility with older workflow definitions.

Condition-related utilities have also moved to orcheo.edges.conditions.
"""

from orcheo.nodes.logic.utilities import (
    DelayNode,
    ForLoopNode,
    SetVariableNode,
    _build_nested,
)


__all__ = [
    "SetVariableNode",
    "DelayNode",
    "ForLoopNode",
    "_build_nested",
]
