"""Registry implementation for Orcheo edges."""

from collections.abc import Callable
from pydantic import BaseModel


class EdgeMetadata(BaseModel):
    """Metadata for an edge in the flow.

    Attributes:
        name: Unique identifier for the edge
        description: Human-readable description of the edge's purpose
        category: Edge category, defaults to "logic"
    """

    name: str
    """Unique identifier for the edge."""
    description: str
    """Human-readable description of the edge's purpose."""
    category: str = "logic"
    """Edge category, defaults to "logic"."""


class EdgeRegistry:
    """Registry for managing flow edges and their metadata."""

    def __init__(self) -> None:
        """Initialize an empty edge registry."""
        self._edges: dict[str, Callable] = {}
        self._metadata: dict[str, EdgeMetadata] = {}
        self._aliases: dict[str, str] = {}

    def _resolve_name(self, name: str) -> str | None:
        """Return the canonical name for a registered edge or alias."""
        if name in self._edges:
            return name
        return self._aliases.get(name)

    def _ensure_name_available(self, name: str) -> None:
        """Raise when ``name`` conflicts with an existing edge or alias."""
        if name in self._edges or name in self._aliases:
            msg = f"Edge '{name}' is already registered."
            raise ValueError(msg)

    def register(self, metadata: EdgeMetadata) -> Callable[[Callable], Callable]:
        """Register a new edge with its metadata.

        Args:
            metadata: Edge metadata including name and schemas

        Returns:
            Decorator function that registers the edge implementation
        """

        def decorator(func: Callable) -> Callable:
            self._ensure_name_available(metadata.name)
            self._edges[metadata.name] = func
            self._metadata[metadata.name] = metadata
            return func

        return decorator

    def register_alias(self, alias: str, canonical_name: str) -> None:
        """Register a legacy alias that resolves to ``canonical_name``."""
        resolved = self._resolve_name(canonical_name)
        if resolved is None:
            msg = (
                f"Cannot register alias '{alias}' for unknown edge '{canonical_name}'."
            )
            raise ValueError(msg)
        if alias == resolved:
            return
        self._ensure_name_available(alias)
        self._aliases[alias] = resolved

    def get_edge(self, name: str) -> Callable | None:
        """Get an edge implementation by name.

        Args:
            name: Name of the edge to retrieve

        Returns:
            Edge implementation function or None if not found
        """
        resolved = self._resolve_name(name)
        if resolved is None:
            return None
        return self._edges.get(resolved)

    def get_metadata(self, name: str) -> EdgeMetadata | None:
        """Return metadata for the edge identified by ``name`` if available."""
        resolved = self._resolve_name(name)
        if resolved is None:
            return None
        return self._metadata.get(resolved)

    def list_metadata(self) -> list[EdgeMetadata]:
        """Return all registered edge metadata entries sorted by name."""
        return sorted(self._metadata.values(), key=lambda item: item.name.lower())

    def get_aliases(self, name: str) -> list[str]:
        """Return the legacy aliases registered for ``name``."""
        resolved = self._resolve_name(name)
        if resolved is None:
            return []
        aliases = [
            alias
            for alias, canonical_name in self._aliases.items()
            if canonical_name == resolved
        ]
        return sorted(aliases, key=str.lower)

    def get_metadata_by_callable(self, obj: Callable) -> EdgeMetadata | None:
        """Return metadata associated with a registered callable."""
        for name, registered in self._edges.items():
            if registered is obj:
                return self._metadata.get(name)
            if isinstance(registered, type) and isinstance(obj, registered):
                return self._metadata.get(name)
        return None

    def unregister(self, name: str) -> None:
        """Remove one registered edge and any aliases targeting it."""
        resolved = self._resolve_name(name)
        if resolved is None:
            return
        self._edges.pop(resolved, None)
        self._metadata.pop(resolved, None)
        aliases = [
            alias
            for alias, canonical_name in self._aliases.items()
            if canonical_name == resolved or alias == name
        ]
        for alias in aliases:
            self._aliases.pop(alias, None)


# Global registry instance
edge_registry = EdgeRegistry()


__all__ = ["EdgeMetadata", "EdgeRegistry", "edge_registry"]
