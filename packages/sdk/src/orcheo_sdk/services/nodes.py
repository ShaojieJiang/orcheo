"""Node service operations.

Pure business logic for node operations, shared by CLI and MCP interfaces.
"""

from __future__ import annotations
from typing import Any
from orcheo_sdk.cli.errors import CLIError


def list_nodes_data(tag: str | None = None) -> list[dict[str, Any]]:
    """Get list of registered nodes.

    Args:
        tag: Optional tag filter for nodes

    Returns:
        List of node metadata objects
    """
    from orcheo.nodes.registry import registry

    entries = registry.list_metadata()

    if tag:
        lowered = tag.lower()
        entries = [
            item
            for item in entries
            if lowered in item.category.lower() or lowered in item.name.lower()
        ]

    return [
        {
            "name": item.name,
            "category": item.category,
            "description": item.description,
        }
        for item in entries
    ]


def show_node_data(name: str) -> dict[str, Any]:
    """Get node metadata and schema.

    Args:
        name: Node name

    Returns:
        Dictionary with node metadata and schema

    Raises:
        CLIError: If node is not registered
    """
    from orcheo.nodes.registry import registry

    metadata = registry.get_metadata(name)
    node_cls = registry.get_node(name)

    if metadata is None or node_cls is None:
        raise CLIError(f"Node '{name}' is not registered.")

    result: dict[str, Any] = {
        "name": metadata.name,
        "category": metadata.category,
        "description": metadata.description,
    }

    if hasattr(node_cls, "model_json_schema"):
        result["schema"] = node_cls.model_json_schema()
    else:
        annotations = getattr(node_cls, "__annotations__", {})
        if annotations:
            result["attributes"] = list(annotations.keys())

    return result
