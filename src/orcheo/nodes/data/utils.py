"""Utility helpers shared across data nodes."""

from __future__ import annotations
from collections.abc import Mapping, Sequence
from typing import Any


def _split_path(path: str) -> list[str]:
    """Return a dotted path split into non-empty segments."""
    parts = [segment.strip() for segment in path.split(".") if segment.strip()]
    if not parts:
        msg = "Path must contain at least one segment"
        raise ValueError(msg)
    return parts


def _extract_value(payload: Any, path: str) -> tuple[bool, Any]:
    """Return the value found at ``path`` within ``payload`` if present."""
    current = payload
    for segment in _split_path(path):
        if isinstance(current, Mapping):
            if segment not in current:
                return False, None
            current = current[segment]
            continue

        if isinstance(current, Sequence) and not isinstance(
            current, str | bytes | bytearray
        ):
            if not segment.isdigit():
                return False, None
            index = int(segment)
            if index >= len(current):
                return False, None
            current = current[index]
            continue

        return False, None

    return True, current


def _assign_path(target: dict[str, Any], path: str, value: Any) -> None:
    """Assign ``value`` into ``target`` using the dotted ``path``."""
    segments = _split_path(path)
    cursor = target
    for segment in segments[:-1]:
        existing = cursor.get(segment)
        if not isinstance(existing, dict):
            existing = {}
            cursor[segment] = existing
        cursor = existing
    cursor[segments[-1]] = value


def _deep_merge(base: dict[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    """Deep merge ``incoming`` into ``base`` returning the merged dictionary."""
    for key, value in incoming.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            base[key] = _deep_merge(dict(base[key]), value)
        else:
            base[key] = value if not isinstance(value, Mapping) else dict(value)
    return base
