"""Composite SQLite-backed ChatKit store."""

from __future__ import annotations
from orcheo_backend.app.chatkit_store_sqlite.attachments import AttachmentStoreMixin
from orcheo_backend.app.chatkit_store_sqlite.items import ThreadItemStoreMixin
from orcheo_backend.app.chatkit_store_sqlite.threads import ThreadStoreMixin


class SqliteChatKitStore(
    AttachmentStoreMixin,
    ThreadItemStoreMixin,
    ThreadStoreMixin,
):
    """Persist ChatKit threads, messages, and attachments in SQLite."""


__all__ = ["SqliteChatKitStore"]
