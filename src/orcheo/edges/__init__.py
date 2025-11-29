"""Edge system for Orcheo workflow routing.

This module provides edges for conditional routing and branching logic.
Edges handle routing decisions, while nodes handle data transformations.
"""

from orcheo.edges.base import BaseEdge
from orcheo.edges.branching import IfElse, Switch, SwitchCase, While
from orcheo.edges.conditions import ComparisonOperator, Condition
from orcheo.edges.registry import EdgeMetadata, EdgeRegistry, edge_registry


__all__ = [
    "BaseEdge",
    "IfElse",
    "Switch",
    "While",
    "SwitchCase",
    "Condition",
    "ComparisonOperator",
    "EdgeMetadata",
    "EdgeRegistry",
    "edge_registry",
]
