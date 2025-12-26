"""Serialization helpers for the PostgreSQL ChatKit store."""

from __future__ import annotations
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from chatkit.types import Attachment, ThreadItem, ThreadMetadata
from pydantic import TypeAdapter
from orcheo_backend.app.chatkit_store_postgres.utils import (
    compact_json,
    ensure_datetime,
)


_THREAD_ADAPTER: TypeAdapter[ThreadMetadata] = TypeAdapter(ThreadMetadata)
_ITEM_ADAPTER: TypeAdapter[ThreadItem] = TypeAdapter(ThreadItem)
_ATTACHMENT_ADAPTER: TypeAdapter[Attachment] = TypeAdapter(Attachment)


def _coerce_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return ensure_datetime(value)
    if isinstance(value, str):
        return ensure_datetime(datetime.fromisoformat(value))
    raise TypeError("Unsupported datetime value")


def serialize_thread_status(thread: ThreadMetadata) -> str:
    """Serialize the thread status to a compact JSON string."""
    status_payload = (
        thread.status.model_dump(mode="json")
        if hasattr(thread.status, "model_dump")
        else thread.status
    )
    return compact_json(status_payload)


def thread_from_row(row: Mapping[str, Any]) -> ThreadMetadata:
    """Convert a SQL row into a ``ThreadMetadata`` instance."""
    data = {
        "id": row["id"],
        "title": row.get("title"),
        "created_at": _coerce_datetime(row["created_at"]),
        "status": _coerce_json(row["status_json"]),
        "metadata": _coerce_json(row["metadata_json"]),
    }
    return _THREAD_ADAPTER.validate_python(data)


def serialize_item(item: ThreadItem) -> str:
    """Serialize a ``ThreadItem`` to JSON."""
    payload = _ITEM_ADAPTER.dump_python(item, mode="json")
    return compact_json(payload)


def item_from_row(row: Mapping[str, Any]) -> ThreadItem:
    """Convert a SQL row into a ``ThreadItem``."""
    payload = _coerce_json(row["item_json"])
    if payload is None:
        payload = {}
    payload.setdefault("id", row["id"])
    payload.setdefault("thread_id", row["thread_id"])
    created_at = row.get("created_at")
    if created_at is not None:
        payload.setdefault("created_at", created_at)
    if isinstance(payload.get("created_at"), str):
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])
    elif isinstance(payload.get("created_at"), datetime):
        payload["created_at"] = ensure_datetime(payload["created_at"])
    return _ITEM_ADAPTER.validate_python(payload)


def serialize_attachment(attachment: Attachment) -> str:
    """Serialize an attachment definition."""
    payload = _ATTACHMENT_ADAPTER.dump_python(attachment, mode="json")
    return compact_json(payload)


def attachment_from_details(details_json: Any) -> Attachment:
    """Deserialize attachment metadata."""
    payload = _coerce_json(details_json)
    return _ATTACHMENT_ADAPTER.validate_python(payload)


__all__ = [
    "attachment_from_details",
    "item_from_row",
    "serialize_attachment",
    "serialize_item",
    "serialize_thread_status",
    "thread_from_row",
]
