"""Tests for the SQLite-to-PostgreSQL migration tooling."""

from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
from orcheo.tooling import postgres_migration as migration


class TrackingMockCursor:
    """Mock cursor that tracks execute calls."""

    def __init__(self) -> None:
        self.executemany_calls: list[tuple[str, list[tuple[Any, ...]]]] = []
        self.execute_calls: list[tuple[str, Any | None]] = []

    def executemany(self, query: str, rows: list[tuple[Any, ...]]) -> None:
        self.executemany_calls.append((query, list(rows)))

    def execute(self, query: str, params: Any | None = None) -> None:
        self.execute_calls.append((query, params))

    def __enter__(self) -> TrackingMockCursor:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class TrackingMockConnection:
    """Mock connection using TrackingMockCursor."""

    def __init__(self) -> None:
        self.cursor_instance = TrackingMockCursor()
        self.autocommit = False
        self.commits = 0

    def cursor(self) -> TrackingMockCursor:
        return self.cursor_instance

    def commit(self) -> None:
        self.commits += 1

    def __enter__(self) -> TrackingMockConnection:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


def _write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def test_transform_row_parses_json_and_bool(tmp_path: Path) -> None:
    db_path = tmp_path / "sample.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE sample (payload TEXT, is_best INTEGER)")
        conn.execute(
            "INSERT INTO sample (payload, is_best) VALUES (?, ?)",
            (json.dumps({"ok": True}), 1),
        )
        conn.commit()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT payload, is_best FROM sample").fetchone()
        assert row is not None

    spec = migration.TableSpec(
        name="sample",
        sqlite_path=db_path,
        sqlite_table="sample",
        postgres_table="sample",
        columns=("payload", "is_best"),
        order_by=(),
        json_columns=("payload",),
        bool_columns=("is_best",),
    )
    transformed = migration._transform_row(row, spec)

    assert transformed["payload"] == {"ok": True}
    assert transformed["is_best"] is True


def test_export_table_writes_batches(tmp_path: Path) -> None:
    db_path = tmp_path / "workflows.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE workflows "
            "(id TEXT, payload TEXT, created_at TEXT, updated_at TEXT)"
        )
        conn.execute(
            "INSERT INTO workflows VALUES (?, ?, ?, ?)",
            ("wf_1", json.dumps({"name": "one"}), "2024-01-01", "2024-01-01"),
        )
        conn.execute(
            "INSERT INTO workflows VALUES (?, ?, ?, ?)",
            ("wf_2", json.dumps({"name": "two"}), "2024-01-02", "2024-01-02"),
        )
        conn.commit()

    spec = migration.TableSpec(
        name="workflows",
        sqlite_path=db_path,
        sqlite_table="workflows",
        postgres_table="workflows",
        columns=("id", "payload", "created_at", "updated_at"),
        order_by=("id",),
        json_columns=("payload",),
    )

    manifest = migration.export_table(spec, tmp_path / "export", batch_size=1)

    assert manifest.row_count == 2
    assert len(manifest.batches) == 2
    for batch in manifest.batches:
        batch_path = tmp_path / "export" / batch.file
        assert batch_path.exists()
        assert batch.checksum


def test_import_manifest_inserts_batches(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    batch_path = export_dir / "workflows" / "batch_0001.jsonl"
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"id": "wf_1", "payload": {"name": "one"}}
    line = json.dumps(payload).encode("utf-8") + b"\n"
    batch_path.write_bytes(line)
    checksum = hashlib.sha256(line).hexdigest()

    manifest = {
        "version": 1,
        "generated_at": "now",
        "tables": {
            "workflows": {
                "name": "workflows",
                "sqlite_path": "ignored",
                "postgres_table": "workflows",
                "columns": ["id", "payload"],
                "row_count": 1,
                "batches": [
                    {
                        "file": str(batch_path.relative_to(export_dir)),
                        "rows": 1,
                        "checksum": checksum,
                    }
                ],
                "json_columns": ["payload"],
                "bool_columns": [],
                "post_import_sql": [],
            }
        },
    }
    manifest_path = export_dir / "manifest.json"
    _write_manifest(manifest_path, manifest)

    connection = TrackingMockConnection()

    def connect_stub(_: str) -> TrackingMockConnection:
        return connection

    result = migration.import_manifest(
        manifest_path,
        "postgresql://test",
        connection_factory=connect_stub,
    )

    assert result["tables"] == ["workflows"]
    assert connection.cursor_instance.executemany_calls
    insert_sql, rows = connection.cursor_instance.executemany_calls[0]
    assert "INSERT INTO workflows" in insert_sql
    assert rows[0] == ("wf_1", json.dumps({"name": "one"}))


def test_validate_manifest_reports_mismatches(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    manifest = {
        "version": 1,
        "generated_at": "now",
        "tables": {
            "workflows": {
                "name": "workflows",
                "sqlite_path": "ignored",
                "postgres_table": "workflows",
                "columns": ["id"],
                "row_count": 2,
                "batches": [],
                "json_columns": [],
                "bool_columns": [],
                "post_import_sql": [],
            }
        },
    }
    manifest_path = export_dir / "manifest.json"
    _write_manifest(manifest_path, manifest)

    class DummyCursor:
        def execute(self, query: str) -> None:
            return None

        def fetchone(self) -> tuple[int]:
            return (1,)

        def __enter__(self) -> DummyCursor:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    class DummyConnection:
        def cursor(self) -> DummyCursor:
            return DummyCursor()

        def __enter__(self) -> DummyConnection:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

    def connect_stub(_: str) -> DummyConnection:
        return DummyConnection()

    result = migration.validate_manifest(
        manifest_path,
        "postgresql://test",
        connection_factory=connect_stub,
    )

    assert result["ok"] is False
    assert result["mismatches"][0]["table"] == "workflows"
