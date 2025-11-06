from __future__ import annotations
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any


def parse_timestamp(value: Any) -> datetime | None:
    """Convert UNIX timestamps or ISO strings to timezone-aware datetimes."""
    if value is None:
        return None
    result: datetime | None = None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            result = value.replace(tzinfo=UTC)
        else:
            result = value.astimezone(UTC)
    elif isinstance(value, int | float):
        result = datetime.fromtimestamp(value, tz=UTC)
    elif isinstance(value, str):
        try:
            if value.isdigit():
                result = datetime.fromtimestamp(int(value), tz=UTC)
            else:
                result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:  # pragma: no cover - defensive
            result = None
    return result


def coerce_str_items(value: Any) -> set[str]:
    """Convert strings, iterables, or JSON payloads into a set of strings."""
    if value is None:
        return set()
    if isinstance(value, str):
        return _coerce_from_string(value)
    if isinstance(value, Mapping):
        return _coerce_from_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray | str):
        return _coerce_from_sequence(value)

    text = str(value).strip()
    return {text} if text else set()


def parse_string_items(raw: str) -> Any:
    """Return structured data parsed from a string representation."""
    stripped = raw.strip()
    if not stripped:
        return []
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        parts = [part.strip() for part in stripped.replace(",", " ").split()]
        return [part for part in parts if part]


def _coerce_from_string(value: str) -> set[str]:
    parsed = parse_string_items(value)
    if isinstance(parsed, list):
        items: set[str] = set()
        for item in parsed:
            if isinstance(item, str):
                token = item.strip()
                if token:
                    items.add(token)
            else:
                items.update(coerce_str_items(item))
        return items
    return coerce_str_items(parsed)


def _coerce_from_mapping(data: Mapping[str, Any]) -> set[str]:
    items: set[str] = set()
    for value in data.values():
        items.update(coerce_str_items(value))
    return items


def _coerce_from_sequence(values: Sequence[Any]) -> set[str]:
    items: set[str] = set()
    for value in values:
        items.update(coerce_str_items(value))
    return items
