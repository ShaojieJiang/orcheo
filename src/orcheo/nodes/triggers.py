"""Trigger nodes bridging orchestration layer with workflow graphs."""

from __future__ import annotations
from dataclasses import field
from typing import Any
from langchain_core.runnables import RunnableConfig
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="WebhookTrigger",
        description="Validate inbound webhook payloads before dispatching runs",
        category="trigger",
    )
)
class WebhookTriggerNode(TaskNode):
    """Node responsible for normalising webhook trigger payloads."""

    name: str
    shared_secret: str | None = None
    allowed_methods: list[str] = field(default_factory=lambda: ["POST"])
    rate_limit_per_minute: int = 60

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return configuration payload describing the webhook trigger."""
        return {
            "type": "webhook",
            "name": self.name,
            "allowed_methods": [method.upper() for method in self.allowed_methods],
            "shared_secret_configured": bool(self.shared_secret),
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "state": state.get("inputs", {}),
        }


@registry.register(
    NodeMetadata(
        name="CronTrigger",
        description="Schedule workflow executions using cron expressions",
        category="trigger",
    )
)
class CronTriggerNode(TaskNode):
    """Node producing cron trigger configuration."""

    name: str
    cron: str
    timezone: str = "UTC"
    prevent_overlap: bool = True

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return cron configuration used by the trigger layer."""
        return {
            "type": "cron",
            "name": self.name,
            "cron": self.cron,
            "timezone": self.timezone,
            "prevent_overlap": self.prevent_overlap,
        }


@registry.register(
    NodeMetadata(
        name="ManualTrigger",
        description="Dispatch manual runs for backfills and ad-hoc executions",
        category="trigger",
    )
)
class ManualTriggerNode(TaskNode):
    """Node describing manual trigger dispatch metadata."""

    name: str
    batch_size: int = 1
    notes: str | None = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return manual trigger configuration."""
        return {
            "type": "manual",
            "name": self.name,
            "batch_size": max(1, self.batch_size),
            "notes": self.notes,
        }


@registry.register(
    NodeMetadata(
        name="HttpPollingTrigger",
        description="Poll HTTP endpoints on an interval to trigger workflows",
        category="trigger",
    )
)
class HttpPollingTriggerNode(TaskNode):
    """Node defining HTTP polling behaviour for triggers."""

    name: str
    url: str
    interval_seconds: int = 300
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return HTTP polling configuration payload."""
        return {
            "type": "http_polling",
            "name": self.name,
            "url": self.url,
            "interval_seconds": max(30, self.interval_seconds),
            "method": self.method.upper(),
            "headers": self.headers,
        }


__all__ = [
    "CronTriggerNode",
    "HttpPollingTriggerNode",
    "ManualTriggerNode",
    "WebhookTriggerNode",
]
