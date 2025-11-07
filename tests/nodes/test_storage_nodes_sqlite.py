"""Tests for SQLiteNode behavior split from the monolithic storage module."""

from __future__ import annotations
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.storage import SQLiteNode


@pytest.mark.asyncio
async def test_sqlite_node_executes_queries(tmp_path) -> None:
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
    assert payload["rowcount"] == -1
