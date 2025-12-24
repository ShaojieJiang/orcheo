"""Core behavior tests for the PostgreSQL-backed ChatKit store."""

from __future__ import annotations
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import pytest
from chatkit.types import (
    FileAttachment,
    InferenceOptions,
    ThreadMetadata,
    UserMessageItem,
    UserMessageTextContent,
)
from orcheo_backend.app.chatkit_store_postgres import PostgresChatKitStore
from orcheo_backend.app.chatkit_store_postgres import base as pg_base
from orcheo_backend.app.chatkit_store_postgres.schema import (
    POSTGRES_CHATKIT_SCHEMA,
    ensure_schema,
)
from orcheo_backend.app.chatkit_store_postgres.serialization import (
    serialize_item,
    serialize_thread_status,
)


class FakeCursor:
    def __init__(
        self, *, row: dict[str, Any] | None = None, rows: list[Any] | None = None
    ) -> None:
        self._row = row
        self._rows = list(rows or [])

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row

    async def fetchall(self) -> list[Any]:
        return list(self._rows)


class FakeConnection:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.queries: list[tuple[str, Any | None]] = []
        self.commits = 0
        self.rollbacks = 0

    async def execute(self, query: str, params: Any | None = None) -> FakeCursor:
        self.queries.append((query.strip(), params))
        response = self._responses.pop(0) if self._responses else {}
        if isinstance(response, FakeCursor):
            return response
        if isinstance(response, dict):
            return FakeCursor(row=response.get("row"), rows=response.get("rows"))
        if isinstance(response, list):
            return FakeCursor(rows=response)
        return FakeCursor()

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1

    async def __aenter__(self) -> FakeConnection:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        return None


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    async def open(self) -> None:
        return None

    def connection(self) -> FakeConnection:
        return self._connection


def make_store(
    monkeypatch: pytest.MonkeyPatch,
    responses: list[Any],
    *,
    initialized: bool = True,
) -> PostgresChatKitStore:
    monkeypatch.setattr(pg_base, "AsyncConnectionPool", object())
    monkeypatch.setattr(pg_base, "DictRowFactory", object())
    store = PostgresChatKitStore("postgresql://test")
    store._pool = FakePool(FakeConnection(responses))
    store._initialized = initialized
    return store


def _timestamp() -> datetime:
    return datetime.now(tz=UTC)


def _thread_row(thread: ThreadMetadata) -> dict[str, Any]:
    return {
        "id": thread.id,
        "title": thread.title,
        "created_at": thread.created_at,
        "status_json": serialize_thread_status(thread),
        "metadata_json": json.dumps(thread.metadata or {}),
    }


def _item_row(item: UserMessageItem, *, ordinal: int) -> dict[str, Any]:
    return {
        "id": item.id,
        "thread_id": item.thread_id,
        "ordinal": ordinal,
        "item_type": getattr(item, "type", None),
        "item_json": serialize_item(item),
        "created_at": item.created_at,
    }


@pytest.mark.asyncio
async def test_postgres_chatkit_schema_executes_statements() -> None:
    class SchemaConnection:
        def __init__(self) -> None:
            self.statements: list[str] = []

        async def execute(self, stmt: str, params: Any | None = None) -> None:
            self.statements.append(stmt.strip())

    conn = SchemaConnection()
    await ensure_schema(conn)

    expected = [
        stmt.strip()
        for stmt in POSTGRES_CHATKIT_SCHEMA.strip().split(";")
        if stmt.strip()
    ]
    assert len(conn.statements) == len(expected)
    assert "CREATE TABLE IF NOT EXISTS chat_threads" in conn.statements[0]


@pytest.mark.asyncio
async def test_postgres_store_initializes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[FakeConnection] = []

    async def _stub_schema(conn: FakeConnection) -> None:
        calls.append(conn)

    monkeypatch.setattr(pg_base, "ensure_schema", _stub_schema)
    store = make_store(monkeypatch, responses=[], initialized=False)

    await store._ensure_initialized()
    await store._ensure_initialized()

    assert store._initialized is True
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_postgres_store_save_thread_merges_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = make_store(monkeypatch, responses=[])

    class FakeRequest:
        metadata = {"workflow_id": "wf_123", "extra": "data"}

    context = {"chatkit_request": FakeRequest()}
    thread = ThreadMetadata(id="thr_merge", created_at=_timestamp())

    await store.save_thread(thread, context)

    assert thread.metadata["workflow_id"] == "wf_123"
    assert thread.metadata["extra"] == "data"


@pytest.mark.asyncio
async def test_postgres_store_load_threads_and_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thread1 = ThreadMetadata(
        id="thr_1",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        metadata={"workflow_id": "wf_1"},
    )
    thread2 = ThreadMetadata(
        id="thr_2",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
        metadata={"workflow_id": "wf_1"},
    )
    responses = [
        {"row": {"created_at": thread1.created_at, "id": "thr_marker"}},
        {"rows": [_thread_row(thread1), _thread_row(thread2)]},
        {"rows": [_thread_row(thread2)]},
    ]
    store = make_store(monkeypatch, responses=responses)
    context: dict[str, object] = {}

    page = await store.load_threads(
        limit=1, after="thr_marker", order="asc", context=context
    )

    assert page.has_more is True
    assert page.after == "thr_1"
    assert page.data[0].id == "thr_1"

    filtered = await store.filter_threads({"workflow_id": "wf_1"}, limit=10)
    assert filtered.data[0].id == "thr_2"


@pytest.mark.asyncio
async def test_postgres_store_items_and_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = UserMessageItem(
        id="msg_1",
        thread_id="thr_1",
        created_at=_timestamp(),
        content=[UserMessageTextContent(type="input_text", text="Ping")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )
    responses = [
        {"row": {"current": 0}},
        {},
        {},
        {"row": {"ordinal": 0, "id": "msg_marker"}},
        {"rows": [_item_row(item, ordinal=1)]},
        {"row": _item_row(item, ordinal=1)},
        {},
        {},
        {"rows": [_item_row(item, ordinal=1)]},
    ]
    store = make_store(monkeypatch, responses=responses)
    context: dict[str, object] = {}

    await store.add_thread_item(item.thread_id, item, context)

    page = await store.load_thread_items(
        item.thread_id,
        after="msg_marker",
        limit=10,
        order="asc",
        context=context,
    )
    assert page.data[0].id == item.id

    loaded = await store.load_item(item.thread_id, item.id, context)
    assert loaded.id == item.id

    await store.delete_thread_item(item.thread_id, item.id, context)

    search_page = await store.search_thread_items(item.thread_id, "Ping", limit=5)
    assert search_page.data[0].id == item.id


@pytest.mark.asyncio
async def test_postgres_store_save_item_insert_and_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = UserMessageItem(
        id="msg_save",
        thread_id="thr_save",
        created_at=_timestamp(),
        content=[UserMessageTextContent(type="input_text", text="First")],
        attachments=[],
        quoted_text=None,
        inference_options=InferenceOptions(),
    )

    responses_insert = [
        {"row": None},
        {"row": {"current": -1}},
        {},
        {},
    ]
    store_insert = make_store(monkeypatch, responses=responses_insert)
    await store_insert.save_item(item.thread_id, item, context={})

    responses_update = [
        {"row": {"ordinal": 2}},
        {},
        {},
    ]
    store_update = make_store(monkeypatch, responses=responses_update)
    await store_update.save_item(item.thread_id, item, context={})


@pytest.mark.asyncio
async def test_postgres_store_attachments_and_prune(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attachment = FileAttachment(
        id="att_1",
        name="example.txt",
        mime_type="text/plain",
    )
    stored_path = tmp_path / "example.txt"
    stored_path.write_text("sample", encoding="utf-8")

    responses = [
        {},
        {"row": {"details_json": attachment.model_dump(mode="json")}},
        {},
        {"rows": [{"id": "thr_prune"}]},
        {"rows": [{"storage_path": str(stored_path)}]},
        {},
        {},
    ]
    store = make_store(monkeypatch, responses=responses)

    await store.save_attachment(attachment, context={}, storage_path=str(stored_path))
    loaded = await store.load_attachment(attachment.id, context={})
    assert loaded.id == attachment.id

    await store.delete_attachment(attachment.id, context={})

    pruned = await store.prune_threads_older_than(datetime(2024, 1, 1, tzinfo=UTC))
    assert pruned == 1
    assert stored_path.exists() is False


@pytest.mark.asyncio
async def test_postgres_store_search_pagination_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify search pagination correctly includes thread_id in the marker query."""
    responses = [
        {"row": {"ordinal": 5, "id": "msg_marker"}},  # Response for the marker query
        {"rows": []},  # Response for the search results
    ]
    store = make_store(monkeypatch, responses=responses)

    thread_id = "thr_search"
    after_id = "msg_marker"

    await store.search_thread_items(
        thread_id=thread_id, query="test query", after=after_id
    )

    # Check the queries executed
    # The first query should be the marker resolution
    connection = store._pool.connection()
    assert len(connection.queries) >= 1

    marker_query, marker_params = connection.queries[0]

    # Verify the marker query SQL contains the thread_id check
    assert "SELECT ordinal, id FROM chat_messages" in marker_query
    assert "WHERE id = %s AND thread_id = %s" in marker_query

    # Verify the parameters passed include both the after ID and the thread ID
    assert marker_params[0] == after_id
    assert marker_params[1] == thread_id
