"""Tests for the SQLite-to-PostgreSQL migration tooling."""

from __future__ import annotations
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
import pytest
from orcheo.tooling import postgres_migration as migration


class MockCopy:
    """Mock copy context manager."""

    def __init__(self) -> None:
        self.rows: list[tuple[Any, ...]] = []

    def write_row(self, row: tuple[Any, ...]) -> None:
        self.rows.append(row)

    def __enter__(self) -> MockCopy:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None


class TrackingMockCursor:
    """Mock cursor that tracks execute calls."""

    def __init__(self) -> None:
        self.executemany_calls: list[tuple[str, list[tuple[Any, ...]]]] = []
        self.execute_calls: list[tuple[str, Any | None]] = []
        self.copy_calls: list[tuple[str, list[tuple[Any, ...]]]] = []

    def executemany(self, query: str, rows: list[tuple[Any, ...]]) -> None:
        self.executemany_calls.append((query, list(rows)))

    def execute(self, query: str, params: Any | None = None) -> None:
        self.execute_calls.append((query, params))

    def copy(self, query: str) -> MockCopy:
        copier = MockCopy()
        self.copy_calls.append((query, copier.rows))
        return copier

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
    assert result["tables"] == ["workflows"]
    assert connection.cursor_instance.copy_calls
    copy_sql, rows = connection.cursor_instance.copy_calls[0]
    assert "COPY workflows" in copy_sql
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

    assert result["mismatches"][0]["table"] == "workflows"


def test_normalize_json_edge_cases() -> None:
    from orcheo.tooling.postgres_migration import _normalize_json

    assert _normalize_json(None) is None
    assert _normalize_json("") is None  # Empty string logic
    assert _normalize_json("  ") is None
    assert _normalize_json('{"a": 1}') == {"a": 1}
    # No need to test malformed json as it would raise JSONDecodeError
    # which isn't caught there (that's fine)


def test_transform_row_nulls() -> None:
    # Test boolean column handling when None
    spec = migration.TableSpec(
        name="t",
        sqlite_path=Path("."),
        sqlite_table="t",
        postgres_table="t",
        columns=("b",),
        order_by=(),
        bool_columns=("b",),
    )

    row = {"b": None}
    transformed = migration._transform_row(row, spec)  # type: ignore
    assert transformed["b"] is False

    row_true = {"b": 1}
    transformed_true = migration._transform_row(row_true, spec)  # type: ignore
    assert transformed_true["b"] is True


def test_main_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # We can mock _build_parser or just pass argv to main
    from orcheo.tooling.postgres_migration import main

    # 1. Export command
    repo_db = tmp_path / "repo.sqlite"
    repo_db.touch()
    chatkit_db = tmp_path / "chatkit.sqlite"
    chatkit_db.touch()

    # Mock build_table_specs and export_all to avoid actual DB work
    monkeypatch.setattr(migration, "build_table_specs", lambda **kwargs: [])
    monkeypatch.setattr(migration, "export_all", lambda *args, **kwargs: {})

    exit_code = main(
        [
            "export",
            "--output",
            str(tmp_path),
            "--repository-sqlite",
            str(repo_db),
            "--chatkit-sqlite",
            str(chatkit_db),
        ]
    )
    assert exit_code == 0

    # 2. Import command
    monkeypatch.setattr(migration, "import_manifest", lambda *args, **kwargs: {})
    manifest = tmp_path / "manifest.json"
    manifest.touch()

    exit_code = main(
        ["import", "--input", str(tmp_path), "--postgres-dsn", "postgres://test"]
    )
    assert exit_code == 0

    # 3. Validate command
    monkeypatch.setattr(
        migration, "validate_manifest", lambda *args, **kwargs: {"ok": True}
    )

    exit_code = main(
        ["validate", "--input", str(tmp_path), "--postgres-dsn", "postgres://test"]
    )
    assert exit_code == 0


def test_import_manifest_resume(tmp_path: Path) -> None:
    # Create manifest and import_state.json
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # batch1 is already done
    batch1_path = export_dir / "t1" / "b1.jsonl"
    batch1_path.parent.mkdir(parents=True, exist_ok=True)
    batch1_path.write_text('{"a":1}')  # Needs proper content for checksum
    import hashlib

    c1 = hashlib.sha256(b'{"a":1}').hexdigest()

    # batch2 is new
    batch2_path = export_dir / "t1" / "b2.jsonl"
    batch2_path.write_text('{"a":2}')
    c2 = hashlib.sha256(b'{"a":2}').hexdigest()

    manifest = {
        "tables": {
            "t1": {
                "postgres_table": "t1",
                "columns": ["a"],
                "batches": [
                    {"file": "t1/b1.jsonl", "checksum": c1},
                    {"file": "t1/b2.jsonl", "checksum": c2},
                ],
            }
        }
    }
    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    state_path = export_dir / "import_state.json"
    state_path.write_text(json.dumps({"completed_batches": ["t1/b1.jsonl"]}))

    connection = TrackingMockConnection()

    def connect_stub(_: str) -> TrackingMockConnection:
        return connection

    migration.import_manifest(
        manifest_path, "dsn", resume=True, connection_factory=connect_stub
    )

    # Should only copy batch 2
    assert len(connection.cursor_instance.copy_calls) == 1
    # Check that state was updated
    new_state = json.loads(state_path.read_text())
    assert "t1/b2.jsonl" in new_state["completed_batches"]


def test_export_table_validations(tmp_path: Path) -> None:
    spec = migration.TableSpec("n", Path("missing"), "t", "t", (), ())

    with pytest.raises(ValueError, match="positive"):
        migration.export_table(spec, tmp_path, batch_size=0)

    with pytest.raises(FileNotFoundError):
        migration.export_table(spec, tmp_path, batch_size=1)


def test_normalize_json_with_empty_string(tmp_path: Path) -> None:
    """Test _normalize_json with whitespace-only strings."""
    from orcheo.tooling.postgres_migration import _normalize_json

    assert _normalize_json("   \t\n  ") is None
    assert _normalize_json("") is None


def test_process_table_with_checksum_mismatch(tmp_path: Path) -> None:
    """Test that _process_table raises error on checksum mismatch."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    batch_path = export_dir / "t1" / "b1.jsonl"
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.write_text('{"a":1}')

    table = {
        "postgres_table": "t1",
        "columns": ["a"],
        "batches": [
            {"file": "t1/b1.jsonl", "checksum": "wrong_checksum"},
        ],
    }

    connection = TrackingMockConnection()
    cursor = connection.cursor()

    with pytest.raises(ValueError, match="Checksum mismatch"):
        migration._process_table(
            connection,
            cursor,
            table,
            export_dir,
            set(),
            {"completed_batches": []},
            export_dir / "state.json",
        )


def test_process_table_with_post_import_sql(tmp_path: Path) -> None:
    """Test that _process_table executes post_import_sql."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    batch_path = export_dir / "t1" / "b1.jsonl"
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    line = b'{"a":1}'
    batch_path.write_bytes(line)
    checksum = hashlib.sha256(line).hexdigest()

    table = {
        "postgres_table": "t1",
        "columns": ["a"],
        "batches": [
            {"file": "t1/b1.jsonl", "checksum": checksum},
        ],
        "post_import_sql": ["SELECT setval('seq', 1)"],
    }

    connection = TrackingMockConnection()
    cursor = connection.cursor()
    state_path = export_dir / "state.json"

    migration._process_table(
        connection,
        cursor,
        table,
        export_dir,
        set(),
        {"completed_batches": []},
        state_path,
    )

    # Verify post_import_sql was executed
    assert any("setval" in str(call) for call in cursor.execute_calls)


def test_import_manifest_with_no_resume(tmp_path: Path) -> None:
    """Test import_manifest with resume=False ignores existing state."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    batch_path = export_dir / "t1" / "b1.jsonl"
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    line = b'{"a":1}'
    batch_path.write_bytes(line)
    checksum = hashlib.sha256(line).hexdigest()

    manifest = {
        "tables": {
            "t1": {
                "postgres_table": "t1",
                "columns": ["a"],
                "batches": [
                    {"file": "t1/b1.jsonl", "checksum": checksum},
                ],
            }
        }
    }
    manifest_path = export_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    # Create old state
    state_path = export_dir / "import_state.json"
    state_path.write_text(json.dumps({"completed_batches": ["t1/b1.jsonl"]}))

    connection = TrackingMockConnection()

    def connect_stub(_: str) -> TrackingMockConnection:
        return connection

    # Import without resume should reprocess everything
    migration.import_manifest(
        manifest_path, "dsn", resume=False, connection_factory=connect_stub
    )

    # Should have processed the batch even though it was in old state
    assert len(connection.cursor_instance.copy_calls) >= 1


def test_validate_manifest_with_psycopg_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test validate_manifest raises error when psycopg is None."""
    monkeypatch.setattr(migration, "psycopg", None)

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"tables": {}}')

    with pytest.raises(RuntimeError, match="psycopg"):
        migration.validate_manifest(manifest_path, "dsn")


def test_import_manifest_with_psycopg_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test import_manifest raises error when psycopg is None."""
    monkeypatch.setattr(migration, "psycopg", None)

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"tables": {}}')

    with pytest.raises(RuntimeError, match="psycopg"):
        migration.import_manifest(manifest_path, "dsn")


def test_resolve_paths_missing_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test _resolve_paths raises when paths are missing."""
    monkeypatch.setattr(migration, "get_settings", lambda: {})
    monkeypatch.setattr(
        migration,
        "load_auth_settings",
        lambda: type("obj", (), {"service_token_db_path": None})(),
    )

    with pytest.raises(ValueError, match="Repository and ChatKit"):
        migration._resolve_paths(
            repository_sqlite=None,
            chatkit_sqlite=None,
            service_token_sqlite=None,
        )


def test_resolve_paths_with_fallback_token_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _resolve_paths uses fallback service token path."""
    repo_path = tmp_path / "repo.sqlite"
    repo_path.touch()
    chatkit_path = tmp_path / "chatkit.sqlite"
    chatkit_path.touch()
    fallback_token_path = tmp_path / "service_tokens.sqlite"
    fallback_token_path.touch()

    monkeypatch.setattr(
        migration,
        "get_settings",
        lambda: {
            "REPOSITORY_SQLITE_PATH": str(repo_path),
            "CHATKIT_SQLITE_PATH": str(chatkit_path),
        },
    )
    monkeypatch.setattr(
        migration,
        "load_auth_settings",
        lambda: type("obj", (), {"service_token_db_path": None})(),
    )

    repo, chatkit, token = migration._resolve_paths(
        repository_sqlite=None,
        chatkit_sqlite=None,
        service_token_sqlite=None,
    )

    assert repo == repo_path
    assert chatkit == chatkit_path
    assert token == fallback_token_path


def test_build_table_specs_without_service_tokens(tmp_path: Path) -> None:
    """Test build_table_specs without service token path."""
    repo_path = tmp_path / "repo.sqlite"
    chatkit_path = tmp_path / "chatkit.sqlite"

    specs = migration.build_table_specs(
        repository_sqlite=repo_path,
        chatkit_sqlite=chatkit_path,
        service_token_sqlite=None,
    )

    # Should not include service_tokens tables
    spec_names = [s.name for s in specs]
    assert "service_tokens" not in spec_names
    assert "service_token_audit_log" not in spec_names
    assert "workflows" in spec_names


def test_main_import_without_postgres_dsn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test main import command raises error without POSTGRES_DSN."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"tables": {}}')

    monkeypatch.setattr(migration, "get_settings", lambda: {})

    with pytest.raises(SystemExit, match="POSTGRES_DSN"):
        migration.main(["import", "--input", str(tmp_path)])


def test_main_validate_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main validate command exits on validation failure."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"tables": {}}')

    monkeypatch.setattr(migration, "get_settings", lambda: {"POSTGRES_DSN": "test"})
    monkeypatch.setattr(
        migration,
        "validate_manifest",
        lambda *args, **kwargs: {"ok": False, "mismatches": [{"table": "test"}]},
    )

    with pytest.raises(SystemExit, match="Validation failed"):
        migration.main(["validate", "--input", str(tmp_path)])


def test_main_unknown_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main with unknown command raises error."""
    mock_args = type(
        "args", (), {"command": "unknown", "postgres_dsn": "test", "input": Path(".")}
    )()

    class MockParser:
        def parse_args(self, argv: list[str] | None = None) -> Any:
            return mock_args

    monkeypatch.setattr(migration, "_build_parser", lambda: MockParser())
    monkeypatch.setattr(migration, "get_settings", lambda: {"POSTGRES_DSN": "test"})

    with pytest.raises(SystemExit, match="Unknown command"):
        migration.main([])


def test_now_iso_returns_isoformat() -> None:
    """Test _now_iso returns an ISO format string."""
    result = migration._now_iso()
    assert isinstance(result, str)
    # Should be parseable as ISO format
    from datetime import datetime

    datetime.fromisoformat(result.replace("Z", "+00:00"))


def test_normalize_json_with_non_string_value() -> None:
    """Test _normalize_json returns non-string values as-is."""
    # Test with dict
    result = migration._normalize_json({"key": "value"})
    assert result == {"key": "value"}

    # Test with list
    result = migration._normalize_json([1, 2, 3])
    assert result == [1, 2, 3]

    # Test with int
    result = migration._normalize_json(42)
    assert result == 42


def test_export_all_generates_manifest(tmp_path: Path) -> None:
    """Test export_all exports multiple tables and generates manifest."""
    db_path = tmp_path / "test.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE t1 (id TEXT)")
        conn.execute("CREATE TABLE t2 (id TEXT)")
        conn.execute("INSERT INTO t1 VALUES ('a')")
        conn.execute("INSERT INTO t2 VALUES ('b')")
        conn.commit()

    specs = [
        migration.TableSpec(
            name="t1",
            sqlite_path=db_path,
            sqlite_table="t1",
            postgres_table="t1",
            columns=("id",),
            order_by=("id",),
        ),
        migration.TableSpec(
            name="t2",
            sqlite_path=db_path,
            sqlite_table="t2",
            postgres_table="t2",
            columns=("id",),
            order_by=("id",),
        ),
    ]

    output_dir = tmp_path / "export"
    result = migration.export_all(specs, output_dir, batch_size=1000)

    # Manifest should have version and tables
    assert result["version"] == 1
    assert "generated_at" in result
    assert "t1" in result["tables"]
    assert "t2" in result["tables"]

    # Manifest file should be written
    manifest_path = output_dir / "manifest.json"
    assert manifest_path.exists()
    stored = json.loads(manifest_path.read_text())
    assert stored["version"] == 1


def test_process_table_with_empty_batch(tmp_path: Path) -> None:
    """Test _process_table handles batch with no rows gracefully."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()

    # Create an empty batch file
    batch_path = export_dir / "t1" / "b1.jsonl"
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.write_bytes(b"")  # Empty file
    checksum = hashlib.sha256(b"").hexdigest()

    table = {
        "postgres_table": "t1",
        "columns": ["a"],
        "batches": [
            {"file": "t1/b1.jsonl", "checksum": checksum},
        ],
    }

    connection = TrackingMockConnection()
    cursor = connection.cursor()
    state_path = export_dir / "state.json"

    migration._process_table(
        connection,
        cursor,
        table,
        export_dir,
        set(),
        {"completed_batches": []},
        state_path,
    )

    # Should not have any copy calls since rows list is empty
    assert len(cursor.copy_calls) == 0


def test_validate_manifest_no_mismatches(tmp_path: Path) -> None:
    """Test validate_manifest returns ok when counts match."""
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
                "row_count": 5,  # Expecting 5 rows
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
            return (5,)  # Return 5 rows to match expected

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

    assert result["ok"] is True
    assert result["mismatches"] == []


def test_validate_manifest_fetchone_returns_none(tmp_path: Path) -> None:
    """Test validate_manifest handles fetchone returning None."""
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    manifest = {
        "version": 1,
        "generated_at": "now",
        "tables": {
            "workflows": {
                "name": "workflows",
                "postgres_table": "workflows",
                "row_count": 1,
                "batches": [],
            }
        },
    }
    manifest_path = export_dir / "manifest.json"
    _write_manifest(manifest_path, manifest)

    class DummyCursor:
        def execute(self, query: str) -> None:
            return None

        def fetchone(self) -> None:
            return None  # Return None

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

    # count should be 0 when row is None, so there's a mismatch
    assert result["ok"] is False
    assert result["mismatches"][0]["actual"] == 0


def test_resolve_paths_no_fallback_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _resolve_paths when no fallback token path exists."""
    repo_path = tmp_path / "repo.sqlite"
    repo_path.touch()
    chatkit_path = tmp_path / "chatkit.sqlite"
    chatkit_path.touch()
    # Do NOT create the fallback token path

    monkeypatch.setattr(
        migration,
        "get_settings",
        lambda: {
            "REPOSITORY_SQLITE_PATH": str(repo_path),
            "CHATKIT_SQLITE_PATH": str(chatkit_path),
        },
    )
    monkeypatch.setattr(
        migration,
        "load_auth_settings",
        lambda: type("obj", (), {"service_token_db_path": None})(),
    )

    repo, chatkit, token = migration._resolve_paths(
        repository_sqlite=None,
        chatkit_sqlite=None,
        service_token_sqlite=None,
    )

    assert repo == repo_path
    assert chatkit == chatkit_path
    assert token is None  # No fallback should be found


def test_build_table_specs_with_service_tokens(tmp_path: Path) -> None:
    """Test build_table_specs includes service token tables when path is provided."""
    repo_path = tmp_path / "repo.sqlite"
    chatkit_path = tmp_path / "chatkit.sqlite"
    token_path = tmp_path / "tokens.sqlite"

    specs = migration.build_table_specs(
        repository_sqlite=repo_path,
        chatkit_sqlite=chatkit_path,
        service_token_sqlite=token_path,
    )

    spec_names = [s.name for s in specs]
    assert "service_tokens" in spec_names
    assert "service_token_audit_log" in spec_names

    # Check post_import_sql for audit_log
    audit_spec = next(s for s in specs if s.name == "service_token_audit_log")
    assert len(audit_spec.post_import_sql) > 0
    assert "setval" in audit_spec.post_import_sql[0]


def test_import_manifest_uses_psycopg_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test import_manifest uses psycopg.connect when no factory is provided."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"tables": {}}')

    connection = TrackingMockConnection()

    def mock_connect(*args: Any, **kwargs: Any) -> TrackingMockConnection:
        return connection

    mock_psycopg = type("obj", (), {"connect": mock_connect})()
    monkeypatch.setattr(migration, "psycopg", mock_psycopg)

    # This should now hit line 262
    result = migration.import_manifest(manifest_path, "dsn", connection_factory=None)
    assert result == {"tables": []}


def test_validate_manifest_uses_psycopg_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test validate_manifest uses psycopg.connect when no factory is provided."""
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"tables": {}}')

    connection = TrackingMockConnection()

    def mock_connect(*args: Any, **kwargs: Any) -> TrackingMockConnection:
        return connection

    mock_psycopg = type("obj", (), {"connect": mock_connect})()
    monkeypatch.setattr(migration, "psycopg", mock_psycopg)

    # This should now hit line 293
    result = migration.validate_manifest(manifest_path, "dsn", connection_factory=None)
    assert result["ok"] is True
