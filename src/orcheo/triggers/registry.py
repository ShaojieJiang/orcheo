"""Registry for external trigger platform factories."""

from __future__ import annotations
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from pydantic import BaseModel


class TriggerMetadata(BaseModel):
    """Metadata for a trigger platform."""

    id: str
    display_name: str
    description: str = ""


@dataclass(slots=True)
class TriggerRegistration:
    """Registered trigger factory and metadata."""

    metadata: TriggerMetadata
    factory: Callable[..., Any]


class TriggerRegistry:
    """Registry for built-in and plugin-provided trigger types."""

    def __init__(self) -> None:
        """Initialize an empty trigger registry."""
        self._registrations: dict[str, TriggerRegistration] = {}

    def register(self, metadata: TriggerMetadata, factory: Callable[..., Any]) -> None:
        """Register a trigger type."""
        if metadata.id in self._registrations:
            msg = f"Trigger '{metadata.id}' is already registered."
            raise ValueError(msg)
        self._registrations[metadata.id] = TriggerRegistration(
            metadata=metadata,
            factory=factory,
        )

    def get(self, trigger_id: str) -> TriggerRegistration | None:
        """Return one trigger registration by identifier."""
        return self._registrations.get(trigger_id)

    def list_metadata(self) -> list[TriggerMetadata]:
        """Return all known trigger metadata entries."""
        return sorted(
            (registration.metadata for registration in self._registrations.values()),
            key=lambda item: item.id.lower(),
        )

    def unregister(self, trigger_id: str) -> None:
        """Remove one trigger registration if present."""
        self._registrations.pop(trigger_id, None)


trigger_registry = TriggerRegistry()


__all__ = [
    "TriggerMetadata",
    "TriggerRegistration",
    "TriggerRegistry",
    "trigger_registry",
]
