"""Helpers for converting history payloads into JSON-safe values."""

from __future__ import annotations
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID


_MISSING = object()


def normalize_json_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a JSON-safe mapping with string keys."""
    if value is None:
        return {}
    normalized = normalize_json_value(value)
    if isinstance(normalized, dict):
        return normalized
    return {"value": normalized}


def normalize_json_value(value: Any) -> Any:
    """Return a JSON-safe representation for ``value``."""
    return _normalize_json_value(value, seen=set())


def _normalize_json_value(value: Any, *, seen: set[int]) -> Any:
    scalar_value = _normalize_scalar(value)
    if scalar_value is not _MISSING:
        return scalar_value

    marker = id(value)
    if marker in seen:
        return "<recursive>"

    seen.add(marker)
    try:
        return _normalize_with_handlers(value, seen=seen)
    finally:
        seen.remove(marker)


def _normalize_scalar(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, UUID | Path | Decimal):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Enum):
        return value.value
    return _MISSING


def _normalize_with_handlers(value: Any, *, seen: set[int]) -> Any:
    for handler in (
        _normalize_mapping,
        _normalize_sequence,
        _normalize_set,
        _normalize_dataclass,
        _normalize_model_dump,
        _normalize_object_dict,
    ):
        normalized = handler(value, seen=seen)
        if normalized is not _MISSING:
            return normalized
    return str(value)


def _normalize_mapping(value: Any, *, seen: set[int]) -> Any:
    if not isinstance(value, Mapping):
        return _MISSING
    return {
        str(key): _normalize_json_value(item, seen=seen) for key, item in value.items()
    }


def _normalize_sequence(value: Any, *, seen: set[int]) -> Any:
    if not isinstance(value, list | tuple):
        return _MISSING
    return [_normalize_json_value(item, seen=seen) for item in value]


def _normalize_set(value: Any, *, seen: set[int]) -> Any:
    if not isinstance(value, set | frozenset):
        return _MISSING
    return [_normalize_json_value(item, seen=seen) for item in value]


def _normalize_dataclass(value: Any, *, seen: set[int]) -> Any:
    if not is_dataclass(value) or isinstance(value, type):
        return _MISSING
    return {
        field.name: _normalize_json_value(getattr(value, field.name), seen=seen)
        for field in fields(value)
    }


def _normalize_model_dump(value: Any, *, seen: set[int]) -> Any:
    dumped = _try_model_dump(value)
    if dumped is None:
        return _MISSING
    return _normalize_json_value(dumped, seen=seen)


def _normalize_object_dict(value: Any, *, seen: set[int]) -> Any:
    if not hasattr(value, "__dict__"):
        return _MISSING
    try:
        payload = vars(value)
    except TypeError:
        return _MISSING
    return {
        str(key): _normalize_json_value(item, seen=seen)
        for key, item in payload.items()
    }


def _try_model_dump(value: Any) -> Any | None:
    """Best-effort call to ``model_dump`` when available."""
    model_dump = getattr(value, "model_dump", None)
    if not callable(model_dump):
        return None

    for kwargs in ({"mode": "json"}, {}):
        try:
            return model_dump(**kwargs)
        except TypeError:
            continue
        except Exception:
            return None
    return None


__all__ = ["normalize_json_mapping", "normalize_json_value"]
