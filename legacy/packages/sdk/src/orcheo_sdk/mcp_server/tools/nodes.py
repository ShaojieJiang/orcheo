"""Node catalog MCP tools."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.services import list_nodes_data, show_node_data


def list_nodes(tag: str | None = None) -> list[dict[str, Any]]:
    """List registered nodes with metadata."""
    return list_nodes_data(tag=tag)


def show_node(name: str) -> dict[str, Any]:
    """Display metadata and schema information for a node."""
    return show_node_data(name)


__all__ = ["list_nodes", "show_node"]
