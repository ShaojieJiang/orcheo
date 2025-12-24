"""Composite PostgreSQL-backed ChatKit store."""

from __future__ import annotations
from orcheo_backend.app.chatkit_store_postgres.attachments import AttachmentStoreMixin
from orcheo_backend.app.chatkit_store_postgres.items import ThreadItemStoreMixin
from orcheo_backend.app.chatkit_store_postgres.threads import ThreadStoreMixin


class PostgresChatKitStore(
    AttachmentStoreMixin,
    ThreadItemStoreMixin,
    ThreadStoreMixin,
):
    """Persist ChatKit threads, messages, and attachments in PostgreSQL."""


__all__ = ["PostgresChatKitStore"]
