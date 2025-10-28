"""Registry implementation for Orcheo nodes."""

from __future__ import annotations
from collections.abc import Callable, Iterable
from pydantic import BaseModel, Field


class NodeMetadata(BaseModel):
    """Metadata for a node in the flow.

    Attributes:
        name: Unique identifier for the node
        description: Human-readable description of the node's purpose
        category: Node category, defaults to "general"
    """

    name: str
    """Unique identifier for the node."""
    description: str
    """Human-readable description of the node's purpose."""
    category: str = "general"
    """Node category, defaults to "general"."""
    tags: list[str] = Field(default_factory=list)
    """Optional set of discoverability tags for the node."""


class NodeRegistry:
    """Registry for managing flow nodes and their metadata."""

    def __init__(self) -> None:
        """Initialize an empty node registry."""
        self._nodes: dict[str, Callable] = {}
        self._metadata: dict[str, NodeMetadata] = {}

    def register(self, metadata: NodeMetadata) -> Callable[[Callable], Callable]:
        """Register a new node with its metadata.

        Args:
            metadata: Node metadata including name and schemas

        Returns:
            Decorator function that registers the node implementation
        """

        def decorator(func: Callable) -> Callable:
            self._nodes[metadata.name] = func
            self._metadata[metadata.name] = metadata
            return func

        return decorator

    def get_node(self, name: str) -> Callable | None:
        """Return a node implementation by name.

        Args:
            name: Name of the node to retrieve

        Returns:
            Node implementation function or ``None`` if not found
        """
        return self._nodes.get(name)

    def get_metadata(self, name: str) -> NodeMetadata | None:
        """Return the metadata associated with a registered node.

        Args:
            name: Name of the node to retrieve metadata for

        Returns:
            Node metadata instance if the node is registered, otherwise ``None``
        """
        return self._metadata.get(name)

    def list_metadata(self) -> list[NodeMetadata]:
        """Return metadata for all registered nodes."""
        return list(self._metadata.values())

    def iter_metadata(self) -> Iterable[NodeMetadata]:
        """Yield metadata objects for registered nodes."""
        yield from self._metadata.values()

    def get_metadata_by_callable(self, obj: Callable) -> NodeMetadata | None:
        """Return metadata associated with a registered callable."""
        for name, registered in self._nodes.items():
            if registered is obj:
                return self._metadata.get(name)
            if isinstance(registered, type) and isinstance(obj, registered):
                return self._metadata.get(name)
        return None


# Global registry instance
registry = NodeRegistry()
