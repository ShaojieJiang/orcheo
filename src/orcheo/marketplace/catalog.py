"""Workflow marketplace catalog utilities."""

from __future__ import annotations
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(slots=True)
class MarketplaceEntry:
    """Describes a reusable marketplace workflow."""

    slug: str
    name: str
    description: str
    tags: tuple[str, ...] = field(default_factory=tuple)


class MarketplaceCatalog:
    """In-memory registry for marketplace entries."""

    def __init__(self) -> None:
        """Create an empty marketplace catalog."""
        self._entries: dict[str, MarketplaceEntry] = {}

    def register(self, entry: MarketplaceEntry) -> None:
        """Add or update a marketplace entry by its slug."""
        self._entries[entry.slug] = entry

    def list(self) -> Iterable[MarketplaceEntry]:
        """Return entries ordered alphabetically by name."""
        return sorted(self._entries.values(), key=lambda entry: entry.name.lower())


__all__ = ["MarketplaceCatalog", "MarketplaceEntry"]
