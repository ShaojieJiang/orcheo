from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, Thread, ThreadItem, ThreadMetadata


@dataclass(slots=True)
class _ThreadState:
    """Container for thread metadata and items."""

    thread: ThreadMetadata
    items: list[ThreadItem]


class MemoryStore(Store[dict[str, Any]]):
    """Minimal in-memory ChatKit store for development purposes."""

    def __init__(self) -> None:
        """Initialize the in-memory state containers."""
        self._threads: dict[str, _ThreadState] = {}

    @staticmethod
    def _coerce_thread_metadata(thread: ThreadMetadata | Thread) -> ThreadMetadata:
        """Return thread metadata without embedded items."""
        has_items = isinstance(thread, Thread) or "items" in getattr(
            thread,
            "model_fields_set",
            set(),
        )
        if not has_items:
            return thread.model_copy(deep=True)

        data = thread.model_dump()
        data.pop("items", None)
        return ThreadMetadata(**data).model_copy(deep=True)

    async def load_thread(
        self, thread_id: str, context: dict[str, Any]
    ) -> ThreadMetadata:
        """Return a persisted thread by identifier."""
        state = self._threads.get(thread_id)
        if state is None:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self._coerce_thread_metadata(state.thread)

    async def save_thread(
        self, thread: ThreadMetadata, context: dict[str, Any]
    ) -> None:
        """Persist thread metadata in memory."""
        metadata = self._coerce_thread_metadata(thread)
        state = self._threads.get(thread.id)
        if state is not None:
            state.thread = metadata
            return
        self._threads[thread.id] = _ThreadState(thread=metadata, items=[])

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadMetadata]:
        """Return a paginated slice of threads."""
        threads = sorted(
            (
                self._coerce_thread_metadata(state.thread)
                for state in self._threads.values()
            ),
            key=lambda thread: thread.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=order == "desc",
        )

        start_index = 0
        if after:
            index_map = {thread.id: idx for idx, thread in enumerate(threads)}
            start_index = index_map.get(after, -1) + 1

        slice_threads = threads[start_index : start_index + limit + 1]
        has_more = len(slice_threads) > limit
        slice_threads = slice_threads[:limit]
        next_after = slice_threads[-1].id if has_more and slice_threads else None

        return Page(data=slice_threads, has_more=has_more, after=next_after)

    async def delete_thread(self, thread_id: str, context: dict[str, Any]) -> None:
        """Remove a stored thread and its items."""
        self._threads.pop(thread_id, None)

    def _items(self, thread_id: str) -> list[ThreadItem]:
        state = self._threads.get(thread_id)
        if state is None:
            state = _ThreadState(
                thread=ThreadMetadata(id=thread_id, created_at=datetime.now(UTC)),
                items=[],
            )
            self._threads[thread_id] = state
        return state.items

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadItem]:
        """Return items stored for the given thread."""
        items = [item.model_copy(deep=True) for item in self._items(thread_id)]
        items.sort(
            key=lambda item: getattr(item, "created_at", datetime.now(UTC)),
            reverse=order == "desc",
        )

        start_index = 0
        if after:
            index_map = {item.id: idx for idx, item in enumerate(items)}
            start_index = index_map.get(after, -1) + 1

        slice_items = items[start_index : start_index + limit + 1]
        has_more = len(slice_items) > limit
        slice_items = slice_items[:limit]
        next_after = slice_items[-1].id if has_more and slice_items else None

        return Page(data=slice_items, has_more=has_more, after=next_after)

    async def add_thread_item(
        self,
        thread_id: str,
        item: ThreadItem,
        context: dict[str, Any],
    ) -> None:
        """Append a new item to the thread."""
        self._items(thread_id).append(item.model_copy(deep=True))

    async def save_item(
        self,
        thread_id: str,
        item: ThreadItem,
        context: dict[str, Any],
    ) -> None:
        """Update an existing item or insert it if missing."""
        items = self._items(thread_id)
        for index, existing in enumerate(items):
            if existing.id == item.id:
                items[index] = item.model_copy(deep=True)
                return
        items.append(item.model_copy(deep=True))

    async def load_item(
        self,
        thread_id: str,
        item_id: str,
        context: dict[str, Any],
    ) -> ThreadItem:
        """Fetch a single thread item."""
        for item in self._items(thread_id):
            if item.id == item_id:
                return item.model_copy(deep=True)
        raise NotFoundError(f"Item {item_id} not found")

    async def delete_thread_item(
        self,
        thread_id: str,
        item_id: str,
        context: dict[str, Any],
    ) -> None:
        """Remove an item from the thread."""
        items = self._items(thread_id)
        self._threads[thread_id].items = [item for item in items if item.id != item_id]

    async def save_attachment(
        self,
        attachment: Attachment,
        context: dict[str, Any],
    ) -> None:  # pragma: no cover - attachments disabled in demo
        """Persist attachment metadata (unsupported for in-memory store)."""
        raise NotImplementedError(
            "In-memory ChatKit store does not persist attachments.",
        )

    async def load_attachment(
        self,
        attachment_id: str,
        context: dict[str, Any],
    ) -> Attachment:  # pragma: no cover - attachments disabled in demo
        """Load attachment metadata (unsupported for in-memory store)."""
        raise NotImplementedError(
            "In-memory ChatKit store does not support attachments.",
        )

    async def delete_attachment(
        self,
        attachment_id: str,
        context: dict[str, Any],
    ) -> None:  # pragma: no cover - attachments disabled in demo
        """Delete attachment metadata (unsupported for in-memory store)."""
        raise NotImplementedError(
            "In-memory ChatKit store does not support attachments.",
        )
