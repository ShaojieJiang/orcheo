"""Storage nodes providing database access."""

from __future__ import annotations
import asyncio
import sqlite3
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, cast
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


if TYPE_CHECKING:
    pass


def _rows_to_dicts(
    columns: Sequence[str], rows: Sequence[Sequence[Any]]
) -> list[dict[str, Any]]:
    """Convert database rows into dictionaries keyed by column name."""
    return [dict(zip(columns, row, strict=False)) for row in rows]


@registry.register(
    NodeMetadata(
        name="PostgresNode",
        description="Execute SQL against a PostgreSQL database using psycopg.",
        category="storage",
    )
)
class PostgresNode(TaskNode):
    """Node encapsulating basic PostgreSQL interactions."""

    dsn: str = Field(
        default="[[postgres_dsn]]",
        description="PostgreSQL DSN, e.g. postgresql://user:pass@host/db",
    )
    query: str = Field(description="SQL query to execute")
    parameters: Mapping[str, Any] | Sequence[Any] | None = Field(
        default=None, description="Parameters bound to the SQL query"
    )
    fetch: Literal["none", "one", "all"] = Field(
        default="all", description="Fetch strategy for returning result rows"
    )
    autocommit: bool = Field(
        default=True, description="Enable autocommit mode for the connection"
    )

    def _execute(self) -> dict[str, Any]:
        """Execute the configured query returning structured results."""
        import psycopg

        with psycopg.connect(self.dsn) as connection:
            connection.autocommit = self.autocommit
            with connection.cursor() as cursor:
                cursor.execute(self.query, self.parameters)

                if self.fetch == "none":
                    return {"rows": [], "rowcount": cursor.rowcount}

                row = cursor.fetchone() if self.fetch == "one" else cursor.fetchall()
                if cursor.description is None:
                    if self.fetch == "one":
                        if row is None:
                            raw_rows: list[Sequence[Any]] = []
                        else:
                            raw_rows = [cast(Sequence[Any], row)]
                    else:
                        raw_rows = list(cast(Sequence[Sequence[Any]], row))
                    return {"rows": raw_rows, "rowcount": cursor.rowcount}

                columns = [column.name for column in cursor.description]
                if self.fetch == "one":
                    if row is None:
                        data_rows: list[Sequence[Any]] = []
                    else:
                        data_rows = [cast(Sequence[Any], row)]
                else:
                    data_rows = list(cast(Sequence[Sequence[Any]], row))

                if data_rows:
                    first_row = data_rows[0]
                    if len(columns) != len(first_row):
                        return {"rows": data_rows, "rowcount": cursor.rowcount}

                mapped_rows = _rows_to_dicts(columns, data_rows)
                return {"rows": mapped_rows, "rowcount": cursor.rowcount}

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the SQL query asynchronously."""
        return await asyncio.to_thread(self._execute)


@registry.register(
    NodeMetadata(
        name="SQLiteNode",
        description="Execute SQL statements against a SQLite database.",
        category="storage",
    )
)
class SQLiteNode(TaskNode):
    """Node providing simple SQLite access suitable for local workflows."""

    database: str = Field(default=":memory:", description="SQLite database path")
    query: str = Field(description="SQL query to execute")
    parameters: Mapping[str, Any] | Sequence[Any] | None = Field(
        default=None, description="Parameters bound to the SQL query"
    )
    fetch: Literal["none", "one", "all"] = Field(
        default="all", description="Fetch strategy for returning result rows"
    )

    def _execute(self) -> dict[str, Any]:
        """Execute the SQL query returning structured results."""
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.execute(self.query, self.parameters or [])
            connection.commit()

            if self.fetch == "none":
                return {"rows": [], "rowcount": cursor.rowcount}

            if self.fetch == "one":
                row = cursor.fetchone()
                if row is None:
                    return {"rows": [], "rowcount": cursor.rowcount}
                return {
                    "rows": [dict(row)],
                    "rowcount": cursor.rowcount,
                }

            rows = cursor.fetchall()
            return {
                "rows": [dict(item) for item in rows],
                "rowcount": cursor.rowcount,
            }
        finally:
            connection.close()

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Execute the SQLite query asynchronously."""
        return await asyncio.to_thread(self._execute)


__all__ = ["PostgresNode", "SQLiteNode"]
