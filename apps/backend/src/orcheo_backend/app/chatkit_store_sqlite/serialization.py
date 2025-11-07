"""Serialization helpers for the SQLite ChatKit store."""

from __future__ import annotations
import json
from datetime import datetime
import aiosqlite
from chatkit.types import Attachment, ThreadItem, ThreadMetadata
from pydantic import TypeAdapter
from orcheo_backend.app.chatkit_store_sqlite.utils import compact_json


_THREAD_ADAPTER: TypeAdapter[ThreadMetadata] = TypeAdapter(ThreadMetadata)
_ITEM_ADAPTER: TypeAdapter[ThreadItem] = TypeAdapter(ThreadItem)
_ATTACHMENT_ADAPTER: TypeAdapter[Attachment] = TypeAdapter(Attachment)


def serialize_thread_status(thread: ThreadMetadata) -> str:
    """Serialize the thread status to a compact JSON string."""
    status_payload = (
        thread.status.model_dump(mode="json")
        if hasattr(thread.status, "model_dump")
        else thread.status
    )
    return compact_json(status_payload)


def thread_from_row(row: aiosqlite.Row) -> ThreadMetadata:
    """Convert a SQL row into a ``ThreadMetadata`` instance."""
    data = {
        "id": row["id"],
        "title": row["title"],
        "created_at": datetime.fromisoformat(row["created_at"]),
        "status": json.loads(row["status_json"]),
        "metadata": json.loads(row["metadata_json"]),
    }
    return _THREAD_ADAPTER.validate_python(data)


def serialize_item(item: ThreadItem) -> str:
    """Serialize a ``ThreadItem`` to JSON."""
    payload = _ITEM_ADAPTER.dump_python(item, mode="json")
    return compact_json(payload)


def item_from_row(row: aiosqlite.Row) -> ThreadItem:
    """Convert a SQL row into a ``ThreadItem``."""
    payload = json.loads(row["item_json"])
    payload.setdefault("id", row["id"])
    payload.setdefault("thread_id", row["thread_id"])
    payload.setdefault("created_at", row["created_at"])
    if isinstance(payload.get("created_at"), str):
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])
    return _ITEM_ADAPTER.validate_python(payload)


def serialize_attachment(attachment: Attachment) -> str:
    """Serialize an attachment definition."""
    payload = _ATTACHMENT_ADAPTER.dump_python(attachment, mode="json")
    return compact_json(payload)


def attachment_from_details(details_json: str) -> Attachment:
    """Deserialize attachment metadata."""
    return _ATTACHMENT_ADAPTER.validate_python(json.loads(details_json))


__all__ = [
    "attachment_from_details",
    "item_from_row",
    "serialize_attachment",
    "serialize_item",
    "serialize_thread_status",
    "thread_from_row",
]
