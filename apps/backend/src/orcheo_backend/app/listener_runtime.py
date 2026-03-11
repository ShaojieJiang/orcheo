"""In-process storage for live listener runtime health snapshots."""

from __future__ import annotations
from uuid import UUID
from orcheo.listeners import ListenerHealthSnapshot


class ListenerRuntimeStore:
    """Hold the latest listener health snapshots published by a runtime."""

    def __init__(self) -> None:
        """Initialize an empty runtime-health store."""
        self._snapshots: dict[UUID, ListenerHealthSnapshot] = {}

    def list_health(self) -> list[ListenerHealthSnapshot]:
        """Return all tracked listener health snapshots."""
        return [snapshot.model_copy(deep=True) for snapshot in self._snapshots.values()]

    def get_health(self, subscription_id: UUID) -> ListenerHealthSnapshot | None:
        """Return the latest snapshot for one listener subscription."""
        snapshot = self._snapshots.get(subscription_id)
        return snapshot.model_copy(deep=True) if snapshot is not None else None

    def update(self, snapshot: ListenerHealthSnapshot) -> None:
        """Store the latest snapshot for the subscription."""
        self._snapshots[snapshot.subscription_id] = snapshot.model_copy(deep=True)

    def replace_all(self, snapshots: list[ListenerHealthSnapshot]) -> None:
        """Replace the complete snapshot set."""
        self._snapshots = {
            snapshot.subscription_id: snapshot.model_copy(deep=True)
            for snapshot in snapshots
        }

    def clear(self) -> None:
        """Remove all stored listener snapshots."""
        self._snapshots.clear()


__all__ = ["ListenerRuntimeStore"]
