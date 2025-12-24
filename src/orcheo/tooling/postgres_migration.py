"""SQLite-to-PostgreSQL migration tooling for local hosting."""

from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from orcheo.config import get_settings
from orcheo_backend.app.authentication.settings import load_auth_settings


psycopg: Any | None
try:  # pragma: no cover - optional dependency
    import psycopg  # type: ignore[no-redef]
except Exception:  # pragma: no cover - optional dependency
    psycopg = None


@dataclass(frozen=True)
class BatchInfo:
    """Metadata for a single batch export file."""

    file: str
    rows: int
    checksum: str


@dataclass(frozen=True)
class TableManifest:
    """Manifest metadata for a migrated table."""

    name: str
    sqlite_path: str
    postgres_table: str
    columns: tuple[str, ...]
    row_count: int
    batches: list[BatchInfo]
    json_columns: tuple[str, ...]
    bool_columns: tuple[str, ...]
    post_import_sql: tuple[str, ...]


@dataclass(frozen=True)
class TableSpec:
    """Specification for exporting/importing a single table."""

    name: str
    sqlite_path: Path
    sqlite_table: str
    postgres_table: str
    columns: tuple[str, ...]
    order_by: tuple[str, ...]
    json_columns: tuple[str, ...] = ()
    bool_columns: tuple[str, ...] = ()
    post_import_sql: tuple[str, ...] = ()


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _normalize_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        return json.loads(stripped)
    return value


def _transform_row(row: sqlite3.Row, spec: TableSpec) -> dict[str, Any]:
    data = {column: row[column] for column in spec.columns}
    for column in spec.json_columns:
        data[column] = _normalize_json(data.get(column))
    for column in spec.bool_columns:
        if data.get(column) is None:
            data[column] = False
        else:
            data[column] = bool(data[column])
    return data


def _select_sql(spec: TableSpec) -> str:
    columns = ", ".join(spec.columns)
    order_clause = f" ORDER BY {', '.join(spec.order_by)}" if spec.order_by else ""
    return f"SELECT {columns} FROM {spec.sqlite_table}{order_clause}"


def _batch_file_path(output_dir: Path, spec: TableSpec, batch_index: int) -> Path:
    table_dir = output_dir / spec.name
    table_dir.mkdir(parents=True, exist_ok=True)
    return table_dir / f"batch_{batch_index:04d}.jsonl"


def export_table(
    spec: TableSpec,
    output_dir: Path,
    *,
    batch_size: int,
) -> TableManifest:
    """Export a single SQLite table into JSONL batches."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if not spec.sqlite_path.exists():
        raise FileNotFoundError(f"Missing SQLite database: {spec.sqlite_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    batch_index = 0
    total_rows = 0
    batches: list[BatchInfo] = []

    with sqlite3.connect(spec.sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(_select_sql(spec))

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            batch_index += 1
            batch_path = _batch_file_path(output_dir, spec, batch_index)
            digest = hashlib.sha256()
            row_count = 0

            with batch_path.open("wb") as handle:
                for row in rows:
                    payload = _transform_row(row, spec)
                    line = (
                        json.dumps(
                            payload,
                            separators=(",", ":"),
                            sort_keys=True,
                        ).encode("utf-8")
                        + b"\n"
                    )
                    handle.write(line)
                    digest.update(line)
                    row_count += 1

            batches.append(
                BatchInfo(
                    file=str(batch_path.relative_to(output_dir)),
                    rows=row_count,
                    checksum=digest.hexdigest(),
                )
            )
            total_rows += row_count

    return TableManifest(
        name=spec.name,
        sqlite_path=str(spec.sqlite_path),
        postgres_table=spec.postgres_table,
        columns=spec.columns,
        row_count=total_rows,
        batches=batches,
        json_columns=spec.json_columns,
        bool_columns=spec.bool_columns,
        post_import_sql=spec.post_import_sql,
    )


def export_all(
    specs: Iterable[TableSpec],
    output_dir: Path,
    *,
    batch_size: int,
) -> dict[str, Any]:
    """Export all configured tables into an output directory."""
    manifest: dict[str, Any] = {
        "version": 1,
        "generated_at": _now_iso(),
        "tables": {},
    }

    for spec in specs:
        table_manifest = export_table(spec, output_dir, batch_size=batch_size)
        manifest["tables"][spec.name] = asdict(table_manifest)

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def _prepare_value(value: Any) -> Any:
    if isinstance(value, dict | list):
        return json.dumps(value)
    return value


def _load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"completed_batches": []}
    return json.loads(state_path.read_text())


def _save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True))


def _process_table(
    conn: Any,
    cursor: Any,
    table: dict[str, Any],
    root_dir: Path,
    completed: set[str],
    state: dict[str, Any],
    state_path: Path,
) -> None:
    columns = table["columns"]
    column_list = ", ".join(columns)

    for batch in table["batches"]:
        batch_file = batch["file"]
        if batch_file in completed:
            continue
        batch_path = root_dir / batch_file
        digest = hashlib.sha256(batch_path.read_bytes()).hexdigest()
        if digest != batch["checksum"]:
            msg = f"Checksum mismatch for {batch_file}"
            raise ValueError(msg)

        rows: list[tuple[Any, ...]] = []
        for raw_line in batch_path.read_text().splitlines():
            payload = json.loads(raw_line)
            rows.append(tuple(_prepare_value(payload.get(col)) for col in columns))

        if rows:
            with cursor.copy(
                f"COPY {table['postgres_table']} ({column_list}) FROM STDIN"
            ) as copy:
                for row in rows:
                    copy.write_row(row)
        conn.commit()
        completed.add(batch_file)
        state["completed_batches"] = sorted(completed)
        _save_state(state_path, state)

    for stmt in table.get("post_import_sql", []):
        cursor.execute(stmt)
    conn.commit()


def import_manifest(
    manifest_path: Path,
    dsn: str,
    *,
    resume: bool = True,
    connection_factory: Callable[[str], Any] | None = None,
) -> dict[str, Any]:  # noqa: C901
    """Import all batches described by the manifest into PostgreSQL."""
    if connection_factory is None:
        if psycopg is None:  # pragma: no cover
            msg = "psycopg is required for PostgreSQL imports."
            raise RuntimeError(msg)
        connect = psycopg.connect
    else:
        connect = connection_factory

    manifest = json.loads(manifest_path.read_text())
    root_dir = manifest_path.parent
    state_path = root_dir / "import_state.json"
    state = _load_state(state_path) if resume else {"completed_batches": []}
    completed = set(state.get("completed_batches", []))
    with connect(dsn) as conn:
        conn.autocommit = False
        with conn.cursor() as cursor:
            for _table_name, table in manifest["tables"].items():
                _process_table(
                    conn, cursor, table, root_dir, completed, state, state_path
                )

    return {"tables": list(manifest["tables"].keys())}


def validate_manifest(
    manifest_path: Path,
    dsn: str,
    *,
    connection_factory: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Validate Postgres row counts against the manifest."""
    if connection_factory is None:
        if psycopg is None:  # pragma: no cover
            msg = "psycopg is required for PostgreSQL validation."
            raise RuntimeError(msg)
        connect = psycopg.connect
    else:
        connect = connection_factory

    manifest = json.loads(manifest_path.read_text())
    mismatches: list[dict[str, Any]] = []

    with connect(dsn) as conn:
        with conn.cursor() as cursor:
            for table_name, table in manifest["tables"].items():
                cursor.execute(f"SELECT COUNT(*) FROM {table['postgres_table']}")
                row = cursor.fetchone()
                count = row[0] if row else 0
                if count != table["row_count"]:
                    mismatches.append(
                        {
                            "table": table_name,
                            "expected": table["row_count"],
                            "actual": count,
                        }
                    )

    return {"ok": not mismatches, "mismatches": mismatches}


def _resolve_paths(
    *,
    repository_sqlite: str | None,
    chatkit_sqlite: str | None,
    service_token_sqlite: str | None,
) -> tuple[Path, Path, Path | None]:
    settings = get_settings()
    repo_path = repository_sqlite or settings.get("REPOSITORY_SQLITE_PATH")
    chatkit_path = chatkit_sqlite or settings.get("CHATKIT_SQLITE_PATH")

    auth_settings = load_auth_settings()
    token_path = service_token_sqlite or auth_settings.service_token_db_path
    if token_path is None:
        repo_dir = Path(str(repo_path)).expanduser().parent
        fallback = repo_dir / "service_tokens.sqlite"
        if fallback.exists():
            token_path = str(fallback)

    if not repo_path or not chatkit_path:
        msg = "Repository and ChatKit SQLite paths must be provided."
        raise ValueError(msg)

    return (
        Path(str(repo_path)).expanduser(),
        Path(str(chatkit_path)).expanduser(),
        Path(str(token_path)).expanduser() if token_path else None,
    )


def build_table_specs(
    *,
    repository_sqlite: Path,
    chatkit_sqlite: Path,
    service_token_sqlite: Path | None,
) -> list[TableSpec]:
    """Build migration specs for repository, history, tokens, and ChatKit."""
    specs: list[TableSpec] = [
        TableSpec(
            name="workflows",
            sqlite_path=repository_sqlite,
            sqlite_table="workflows",
            postgres_table="workflows",
            columns=("id", "payload", "created_at", "updated_at"),
            order_by=("id",),
            json_columns=("payload",),
        ),
        TableSpec(
            name="workflow_versions",
            sqlite_path=repository_sqlite,
            sqlite_table="workflow_versions",
            postgres_table="workflow_versions",
            columns=(
                "id",
                "workflow_id",
                "version",
                "payload",
                "created_at",
                "updated_at",
            ),
            order_by=("workflow_id", "version"),
            json_columns=("payload",),
        ),
        TableSpec(
            name="workflow_runs",
            sqlite_path=repository_sqlite,
            sqlite_table="workflow_runs",
            postgres_table="workflow_runs",
            columns=(
                "id",
                "workflow_id",
                "workflow_version_id",
                "status",
                "triggered_by",
                "payload",
                "created_at",
                "updated_at",
            ),
            order_by=("workflow_id", "created_at"),
            json_columns=("payload",),
        ),
        TableSpec(
            name="webhook_triggers",
            sqlite_path=repository_sqlite,
            sqlite_table="webhook_triggers",
            postgres_table="webhook_triggers",
            columns=("workflow_id", "config"),
            order_by=("workflow_id",),
            json_columns=("config",),
        ),
        TableSpec(
            name="cron_triggers",
            sqlite_path=repository_sqlite,
            sqlite_table="cron_triggers",
            postgres_table="cron_triggers",
            columns=("workflow_id", "config"),
            order_by=("workflow_id",),
            json_columns=("config",),
        ),
        TableSpec(
            name="retry_policies",
            sqlite_path=repository_sqlite,
            sqlite_table="retry_policies",
            postgres_table="retry_policies",
            columns=("workflow_id", "config"),
            order_by=("workflow_id",),
            json_columns=("config",),
        ),
        TableSpec(
            name="execution_history",
            sqlite_path=repository_sqlite,
            sqlite_table="execution_history",
            postgres_table="execution_history",
            columns=(
                "execution_id",
                "workflow_id",
                "inputs",
                "runnable_config",
                "tags",
                "callbacks",
                "metadata",
                "run_name",
                "status",
                "started_at",
                "completed_at",
                "error",
                "trace_id",
                "trace_started_at",
                "trace_completed_at",
                "trace_last_span_at",
            ),
            order_by=("execution_id",),
            json_columns=(
                "inputs",
                "runnable_config",
                "tags",
                "callbacks",
                "metadata",
            ),
        ),
        TableSpec(
            name="execution_history_steps",
            sqlite_path=repository_sqlite,
            sqlite_table="execution_history_steps",
            postgres_table="execution_history_steps",
            columns=("execution_id", "step_index", "at", "payload"),
            order_by=("execution_id", "step_index"),
            json_columns=("payload",),
        ),
        TableSpec(
            name="agentensor_checkpoints",
            sqlite_path=repository_sqlite,
            sqlite_table="agentensor_checkpoints",
            postgres_table="agentensor_checkpoints",
            columns=(
                "id",
                "workflow_id",
                "config_version",
                "runnable_config",
                "metrics",
                "metadata",
                "artifact_url",
                "is_best",
                "created_at",
            ),
            order_by=("workflow_id", "config_version"),
            json_columns=("runnable_config", "metrics", "metadata"),
            bool_columns=("is_best",),
        ),
        TableSpec(
            name="chat_threads",
            sqlite_path=chatkit_sqlite,
            sqlite_table="chat_threads",
            postgres_table="chat_threads",
            columns=(
                "id",
                "title",
                "workflow_id",
                "status_json",
                "metadata_json",
                "created_at",
                "updated_at",
            ),
            order_by=("id",),
            json_columns=("status_json", "metadata_json"),
        ),
        TableSpec(
            name="chat_messages",
            sqlite_path=chatkit_sqlite,
            sqlite_table="chat_messages",
            postgres_table="chat_messages",
            columns=(
                "id",
                "thread_id",
                "ordinal",
                "item_type",
                "item_json",
                "created_at",
            ),
            order_by=("thread_id", "ordinal"),
            json_columns=("item_json",),
        ),
        TableSpec(
            name="chat_attachments",
            sqlite_path=chatkit_sqlite,
            sqlite_table="chat_attachments",
            postgres_table="chat_attachments",
            columns=(
                "id",
                "thread_id",
                "attachment_type",
                "name",
                "mime_type",
                "details_json",
                "storage_path",
                "created_at",
            ),
            order_by=("id",),
            json_columns=("details_json",),
        ),
    ]

    if service_token_sqlite is not None:
        specs.extend(
            [
                TableSpec(
                    name="service_tokens",
                    sqlite_path=service_token_sqlite,
                    sqlite_table="service_tokens",
                    postgres_table="service_tokens",
                    columns=(
                        "identifier",
                        "secret_hash",
                        "scopes",
                        "workspace_ids",
                        "created_at",
                        "created_by",
                        "issued_at",
                        "expires_at",
                        "last_used_at",
                        "use_count",
                        "rotation_expires_at",
                        "rotated_to",
                        "rotated_from",
                        "revoked_at",
                        "revoked_by",
                        "revocation_reason",
                        "allowed_ip_ranges",
                        "rate_limit_override",
                    ),
                    order_by=("identifier",),
                    json_columns=("scopes", "workspace_ids", "allowed_ip_ranges"),
                ),
                TableSpec(
                    name="service_token_audit_log",
                    sqlite_path=service_token_sqlite,
                    sqlite_table="service_token_audit_log",
                    postgres_table="service_token_audit_log",
                    columns=(
                        "id",
                        "token_id",
                        "action",
                        "actor",
                        "ip_address",
                        "user_agent",
                        "timestamp",
                        "details",
                    ),
                    order_by=("id",),
                    json_columns=("details",),
                    post_import_sql=(
                        "SELECT setval("
                        "pg_get_serial_sequence('service_token_audit_log', 'id'), "
                        "(SELECT COALESCE(MAX(id), 1) FROM service_token_audit_log)"
                        ")",
                    ),
                ),
            ]
        )

    return specs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export SQLite data and import into PostgreSQL."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="Export SQLite data")
    export_parser.add_argument("--output", type=Path, required=True)
    export_parser.add_argument("--batch-size", type=int, default=1000)
    export_parser.add_argument("--repository-sqlite")
    export_parser.add_argument("--chatkit-sqlite")
    export_parser.add_argument("--service-token-sqlite")

    import_parser = subparsers.add_parser("import", help="Import into Postgres")
    import_parser.add_argument("--input", type=Path, required=True)
    import_parser.add_argument("--postgres-dsn")
    import_parser.add_argument("--no-resume", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate import")
    validate_parser.add_argument("--input", type=Path, required=True)
    validate_parser.add_argument("--postgres-dsn")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for migration tooling."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "export":
        repo_path, chatkit_path, token_path = _resolve_paths(
            repository_sqlite=args.repository_sqlite,
            chatkit_sqlite=args.chatkit_sqlite,
            service_token_sqlite=args.service_token_sqlite,
        )
        specs = build_table_specs(
            repository_sqlite=repo_path,
            chatkit_sqlite=chatkit_path,
            service_token_sqlite=token_path,
        )
        export_all(specs, args.output, batch_size=args.batch_size)
        return 0

    settings = get_settings()
    dsn = args.postgres_dsn or settings.get("POSTGRES_DSN")
    if not dsn:
        raise SystemExit("POSTGRES_DSN must be set for imports or validation")

    manifest_path = args.input / "manifest.json"
    if args.command == "import":
        import_manifest(
            manifest_path,
            str(dsn),
            resume=not args.no_resume,
        )
        return 0

    if args.command == "validate":
        result = validate_manifest(manifest_path, str(dsn))
        if not result["ok"]:
            raise SystemExit("Validation failed; see mismatch report")
        return 0

    raise SystemExit("Unknown command")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
