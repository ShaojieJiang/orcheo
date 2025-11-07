"""Shared helpers for storage node tests."""

from __future__ import annotations
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock


if "psycopg" not in sys.modules:
    sys.modules["psycopg"] = MagicMock()  # type: ignore[assignment]


_FETCHONE_SENTINEL = object()


class DummyCursor:
    """Minimal psycopg cursor stub for testing."""

    def __init__(
        self,
        *,
        description: list[SimpleNamespace] | None = None,
        rows: list[tuple[Any, ...]] | None = None,
        fetchone_result: tuple[Any, ...] | None | object = _FETCHONE_SENTINEL,
        rowcount: int = 1,
    ) -> None:
        self.executed: tuple[str, Any | None] | None = None
        self.rowcount = rowcount
        if description is None and rows is None:
            self.description = [
                SimpleNamespace(name="id"),
                SimpleNamespace(name="name"),
            ]
        else:
            self.description = description
        self._rows = rows if rows is not None else [(1, "Ada"), (2, "Grace")]
        self._fetchone_result = fetchone_result

    def __enter__(self) -> DummyCursor:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None

    def execute(self, query: str, parameters: Any | None) -> None:
        self.executed = (query, parameters)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> tuple[Any, ...] | None:
        if self._fetchone_result is not _FETCHONE_SENTINEL:
            return self._fetchone_result
        return self._rows[0] if self._rows else None


class DummyConnection:
    """Minimal psycopg connection stub."""

    def __init__(self, cursor: DummyCursor | None = None) -> None:
        self.autocommit = False
        self.cursor_instance = cursor or DummyCursor()
        self.closed = False

    def cursor(self) -> DummyCursor:
        return self.cursor_instance

    def __enter__(self) -> DummyConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.closed = True
