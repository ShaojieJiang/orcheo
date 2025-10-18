"""Storage and communication nodes for Orcheo."""

from __future__ import annotations
from dataclasses import field
from typing import Any
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="PostgreSQL",
        description="Execute SQL statements against a PostgreSQL database",
        category="storage",
    )
)
class PostgreSQLNode(TaskNode):
    """Node describing a PostgreSQL query execution."""

    name: str
    dsn: str
    sql: str
    parameters: dict[str, Any] = field(default_factory=dict)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a payload describing the PostgreSQL operation."""
        return {
            "dsn": self.dsn,
            "sql": self.sql,
            "parameters": self.parameters,
        }


@registry.register(
    NodeMetadata(
        name="SQLite",
        description="Execute SQL statements against a SQLite database",
        category="storage",
    )
)
class SQLiteNode(TaskNode):
    """Node describing a SQLite query execution."""

    name: str
    path: str
    sql: str
    parameters: dict[str, Any] = field(default_factory=dict)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a payload describing the SQLite operation."""
        return {
            "path": self.path,
            "sql": self.sql,
            "parameters": self.parameters,
        }


@registry.register(
    NodeMetadata(
        name="Email",
        description="Send transactional emails via configured provider",
        category="communication",
    )
)
class EmailNode(TaskNode):
    """Node describing an email dispatch payload."""

    name: str
    to: list[str]
    subject: str
    body: str

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the email delivery payload."""
        return {
            "to": self.to,
            "subject": self.subject,
            "body": self.body,
        }


@registry.register(
    NodeMetadata(
        name="Discord",
        description="Post messages to Discord channels",
        category="communication",
    )
)
class DiscordNode(TaskNode):
    """Node describing a Discord webhook payload."""

    name: str
    webhook_url: str
    content: str

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return the Discord webhook payload."""
        return {
            "webhook_url": self.webhook_url,
            "content": self.content,
        }


__all__ = [
    "DiscordNode",
    "EmailNode",
    "PostgreSQLNode",
    "SQLiteNode",
]
