"""Edge catalog MCP tools."""

from __future__ import annotations
from typing import Any
from orcheo_sdk.services import list_edges_data, show_edge_data


def list_edges(category: str | None = None) -> list[dict[str, Any]]:
    """List registered edges with metadata."""
    return list_edges_data(category=category)


def show_edge(name: str) -> dict[str, Any]:
    """Display metadata and schema information for an edge."""
    return show_edge_data(name)


__all__ = ["list_edges", "show_edge"]
