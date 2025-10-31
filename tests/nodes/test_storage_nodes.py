"""Tests for storage nodes."""

from __future__ import annotations
import sys
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.storage import PostgresNode, SQLiteNode


# Mock psycopg module if not available
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
        # Only use default description if not explicitly set (including None)
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


@pytest.mark.asyncio
async def test_postgres_node_fetches_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """PostgresNode should execute queries and map rows to dictionaries."""

    dummy_connection = DummyConnection()

    def connect_stub(dsn: str) -> DummyConnection:
        assert dsn == "postgresql://test"
        return dummy_connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT id, name FROM people",
        fetch="all",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]

    assert payload["rows"] == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Grace"},
    ]
    assert payload["rowcount"] == 1
    assert dummy_connection.cursor_instance.executed == (
        "SELECT id, name FROM people",
        None,
    )


@pytest.mark.asyncio
async def test_postgres_node_fetch_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """PostgresNode should fetch a single row when configured."""

    dummy_connection = DummyConnection()

    def connect_stub(_: str) -> DummyConnection:
        return dummy_connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT id, name FROM people",
        fetch="one",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    assert payload["rows"] == [{"id": 1, "name": "Ada"}]


@pytest.mark.asyncio
async def test_postgres_node_fetch_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """PostgresNode should return empty rows when fetch mode is none."""

    connection = DummyConnection()

    def connect_stub(_: str) -> DummyConnection:
        return connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="UPDATE table SET value=1",
        fetch="none",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    assert payload == {"rows": [], "rowcount": connection.cursor_instance.rowcount}


@pytest.mark.asyncio
async def test_postgres_node_handles_missing_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PostgresNode should return raw rows when description is unavailable."""

    # Explicitly pass rows as a non-None value to ensure description stays None
    test_rows = [(1,), (2,)]
    cursor = DummyCursor(description=None, rows=test_rows)
    connection = DummyConnection(cursor=cursor)

    def connect_stub(_: str) -> DummyConnection:
        return connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT count(*) FROM table",
        fetch="all",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    assert payload["rows"] == [(1,), (2,)]


@pytest.mark.asyncio
async def test_postgres_node_fetch_one_no_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """PostgresNode should handle fetch-one returning no results."""

    cursor = DummyCursor(fetchone_result=None)
    connection = DummyConnection(cursor=cursor)

    def connect_stub(_: str) -> DummyConnection:
        return connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT id FROM empty",
        fetch="one",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    assert payload == {"rows": [], "rowcount": connection.cursor_instance.rowcount}


@pytest.mark.asyncio
async def test_sqlite_node_executes_queries(tmp_path) -> None:
    """SQLiteNode should operate against the provided database file."""

    database = tmp_path / "test.db"
    state = State({"results": {}})

    creator = SQLiteNode(
        name="create",
        database=str(database),
        query="CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT)",
        fetch="none",
    )
    await creator(state, RunnableConfig())

    inserter = SQLiteNode(
        name="insert",
        database=str(database),
        query="INSERT INTO people (name) VALUES (?), (?)",
        parameters=["Ada", "Grace"],
        fetch="none",
    )
    await inserter(state, RunnableConfig())

    selector = SQLiteNode(
        name="select",
        database=str(database),
        query="SELECT id, name FROM people ORDER BY id",
    )
    payload = (await selector(state, RunnableConfig()))["results"]["select"]

    assert payload["rows"] == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Grace"},
    ]


@pytest.mark.asyncio
async def test_sqlite_node_fetch_one_returns_empty(tmp_path) -> None:
    """SQLiteNode should return empty results when no rows exist."""

    database = tmp_path / "test_empty.db"
    state = State({"results": {}})

    creator = SQLiteNode(
        name="create",
        database=str(database),
        query="CREATE TABLE items (id INTEGER PRIMARY KEY)",
        fetch="none",
    )
    await creator(state, RunnableConfig())

    selector = SQLiteNode(
        name="select",
        database=str(database),
        query="SELECT id FROM items WHERE id = ?",
        parameters=[1],
        fetch="one",
    )
    payload = (await selector(state, RunnableConfig()))["results"]["select"]

    assert payload["rows"] == []


@pytest.mark.asyncio
async def test_sqlite_node_fetch_one_returns_row(tmp_path) -> None:
    """SQLiteNode should return a single row when fetch=one finds a match."""

    database = tmp_path / "test_one.db"
    state = State({"results": {}})

    creator = SQLiteNode(
        name="create",
        database=str(database),
        query="CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)",
        fetch="none",
    )
    await creator(state, RunnableConfig())

    inserter = SQLiteNode(
        name="insert",
        database=str(database),
        query="INSERT INTO items (name) VALUES (?)",
        parameters=["Test"],
        fetch="none",
    )
    await inserter(state, RunnableConfig())

    selector = SQLiteNode(
        name="select",
        database=str(database),
        query="SELECT id, name FROM items WHERE id = ?",
        parameters=[1],
        fetch="one",
    )
    payload = (await selector(state, RunnableConfig()))["results"]["select"]

    assert payload["rows"] == [{"id": 1, "name": "Test"}]
    # SQLite returns -1 for SELECT rowcount
    assert payload["rowcount"] == -1


@pytest.mark.asyncio
async def test_postgres_node_fetch_one_no_description_no_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PostgresNode should handle fetch-one with no description and no rows."""

    cursor = DummyCursor(description=None, rows=[], fetchone_result=None)
    connection = DummyConnection(cursor=cursor)

    def connect_stub(_: str) -> DummyConnection:
        return connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT count(*) FROM empty",
        fetch="one",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    assert payload == {"rows": [], "rowcount": connection.cursor_instance.rowcount}


@pytest.mark.asyncio
async def test_postgres_node_fetch_one_no_description_with_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PostgresNode should handle fetch-one with no description but with a row."""

    cursor = DummyCursor(description=None, rows=[(42,)], fetchone_result=(42,))
    connection = DummyConnection(cursor=cursor)

    def connect_stub(_: str) -> DummyConnection:
        return connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT count(*) FROM table",
        fetch="one",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    assert payload["rows"] == [(42,)]
    assert payload["rowcount"] == connection.cursor_instance.rowcount


@pytest.mark.asyncio
async def test_postgres_node_fetch_all_no_description_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PostgresNode should handle fetch-all with no description and empty results."""

    cursor = DummyCursor(description=None, rows=[])
    connection = DummyConnection(cursor=cursor)

    def connect_stub(_: str) -> DummyConnection:
        return connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT * FROM empty_table",
        fetch="all",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    assert payload["rows"] == []
    assert payload["rowcount"] == connection.cursor_instance.rowcount


@pytest.mark.asyncio
async def test_postgres_node_fetch_one_with_description_no_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PostgresNode should handle fetch-one with description but no rows."""

    cursor = DummyCursor(
        description=[SimpleNamespace(name="id"), SimpleNamespace(name="name")],
        fetchone_result=None,
    )
    connection = DummyConnection(cursor=cursor)

    def connect_stub(_: str) -> DummyConnection:
        return connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT id, name FROM empty_table WHERE id = 999",
        fetch="one",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    assert payload["rows"] == []
    assert payload["rowcount"] == connection.cursor_instance.rowcount


@pytest.mark.asyncio
async def test_postgres_node_column_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PostgresNode should handle rows with mismatched column counts."""

    # Create a cursor with 2 columns but rows with 3 values
    cursor = DummyCursor(
        description=[SimpleNamespace(name="id"), SimpleNamespace(name="name")],
        rows=[(1, "Ada", "extra"), (2, "Grace", "data")],
    )
    connection = DummyConnection(cursor=cursor)

    def connect_stub(_: str) -> DummyConnection:
        return connection

    monkeypatch.setattr("psycopg.connect", connect_stub)

    node = PostgresNode(
        name="pg",
        dsn="postgresql://test",
        query="SELECT * FROM malformed_table",
        fetch="all",
    )

    state = State({"results": {}})
    payload = (await node(state, RunnableConfig()))["results"]["pg"]
    # Should return raw rows without dict mapping
    assert payload["rows"] == [(1, "Ada", "extra"), (2, "Grace", "data")]
    assert payload["rowcount"] == cursor.rowcount
