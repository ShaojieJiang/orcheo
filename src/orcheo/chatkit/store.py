"""Lightweight in-memory store for ChatKit threads and messages."""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from chatkit.store import NotFoundError, Store
from chatkit.types import Attachment, Page, Thread, ThreadItem, ThreadMetadata


@dataclass
class _ThreadState:
    """Runtime container for a thread and its stored items."""

    thread: ThreadMetadata
    items: list[ThreadItem]


class InMemoryChatKitStore(Store[dict[str, Any]]):
    """Simple in-memory :class:`~chatkit.store.Store` implementation.

    The store keeps thread metadata and items in dictionaries so the
    ChatKit server can satisfy queries from the Orcheo backend without an
    external persistence layer. It is intentionally minimal and does not
    support attachment storage.
    """

    def __init__(self) -> None:
        """Initialise the in-memory structures for ChatKit conversations."""
        self._threads: dict[str, _ThreadState] = {}

    @staticmethod
    def _coerce_thread_metadata(thread: ThreadMetadata | Thread) -> ThreadMetadata:
        """Return thread metadata without any embedded items."""
        has_items = isinstance(thread, Thread) or "items" in getattr(
            thread, "model_fields_set", set()
        )
        if not has_items:
            return thread.model_copy(deep=True)

        data = thread.model_dump()
        data.pop("items", None)
        return ThreadMetadata(**data).model_copy(deep=True)

    async def load_thread(
        self, thread_id: str, context: dict[str, Any]
    ) -> ThreadMetadata:
        """Return metadata for the given thread identifier."""
        state = self._threads.get(thread_id)
        if not state:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self._coerce_thread_metadata(state.thread)

    async def save_thread(
        self, thread: ThreadMetadata, context: dict[str, Any]
    ) -> None:
        """Persist the provided thread metadata in-memory."""
        metadata = self._coerce_thread_metadata(thread)
        state = self._threads.get(thread.id)
        if state:
            state.thread = metadata
        else:
            self._threads[thread.id] = _ThreadState(thread=metadata, items=[])

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: dict[str, Any],
    ) -> Page[ThreadMetadata]:
        """Return a paginated list of stored thread metadata."""
        threads = sorted(
            (
                self._coerce_thread_metadata(state.thread)
                for state in self._threads.values()
            ),
            key=lambda thread: thread.created_at or datetime.min,
            reverse=(order == "desc"),
        )

        if after:
            index_map = {thread.id: idx for idx, thread in enumerate(threads)}
            start = index_map.get(after, -1) + 1
        else:
            start = 0

        slice_threads = threads[start : start + limit + 1]
        has_more = len(slice_threads) > limit
        slice_threads = slice_threads[:limit]
        next_after = slice_threads[-1].id if has_more and slice_threads else None
        return Page(data=slice_threads, has_more=has_more, after=next_after)

    async def delete_thread(self, thread_id: str, context: dict[str, Any]) -> None:
        """Remove the thread from the in-memory index if present."""
        self._threads.pop(thread_id, None)

    # -- Thread items -------------------------------------------------
    def _items(self, thread_id: str) -> list[ThreadItem]:
        state = self._threads.get(thread_id)
        if state is None:
            state = _ThreadState(
                thread=ThreadMetadata(id=thread_id, created_at=datetime.utcnow()),
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
        """Return a paginated set of thread items for a conversation."""
        items = [item.model_copy(deep=True) for item in self._items(thread_id)]
        items.sort(
            key=lambda item: getattr(item, "created_at", datetime.utcnow()),
            reverse=(order == "desc"),
        )

        if after:
            index_map = {item.id: idx for idx, item in enumerate(items)}
            start = index_map.get(after, -1) + 1
        else:
            start = 0

        slice_items = items[start : start + limit + 1]
        has_more = len(slice_items) > limit
        slice_items = slice_items[:limit]
        next_after = slice_items[-1].id if has_more and slice_items else None
        return Page(data=slice_items, has_more=has_more, after=next_after)

    async def add_thread_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        """Append a new item to the specified thread."""
        self._items(thread_id).append(item.model_copy(deep=True))

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: dict[str, Any]
    ) -> None:
        """Insert or update a thread item in the in-memory store."""
        items = self._items(thread_id)
        for index, existing in enumerate(items):
            if existing.id == item.id:
                items[index] = item.model_copy(deep=True)
                return
        items.append(item.model_copy(deep=True))

    async def load_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> ThreadItem:
        """Fetch a thread item by identifier."""
        for item in self._items(thread_id):
            if item.id == item_id:
                return item.model_copy(deep=True)
        raise NotFoundError(f"Item {item_id} not found")

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: dict[str, Any]
    ) -> None:
        """Delete an item from the conversation if it exists."""
        items = self._items(thread_id)
        self._threads[thread_id].items = [item for item in items if item.id != item_id]

    # -- Attachments --------------------------------------------------
    async def save_attachment(
        self,
        attachment: Attachment,
        context: dict[str, Any],
    ) -> None:
        """Raise because attachments require external storage."""
        raise NotImplementedError(
            "In-memory store does not persist attachments. "
            "Provide a secure store implementation before enabling uploads."
        )

    async def load_attachment(
        self, attachment_id: str, context: dict[str, Any]
    ) -> Attachment:
        """Raise because attachments are not stored locally."""
        raise NotImplementedError(
            "In-memory store does not load attachments because they are not persisted."
        )

    async def delete_attachment(
        self, attachment_id: str, context: dict[str, Any]
    ) -> None:
        """Raise because attachment deletion is unsupported."""
        raise NotImplementedError(
            "In-memory store does not delete attachments because they are not "
            "persisted."
        )
