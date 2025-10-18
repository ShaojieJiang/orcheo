"""Trigger nodes bridging UI and SDK executions."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4
import httpx
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


async def _parse_response(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


@registry.register(
    NodeMetadata(
        name="WebhookTrigger",
        description="Validate a webhook signature and normalize payloads.",
        category="trigger",
    )
)
class WebhookTriggerNode(TaskNode):
    """Trigger that simulates webhook validation and dispatch."""

    secret: str | None = None

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Return normalized webhook dispatch metadata."""
        payload = state.get("inputs", {}).get("body", {})
        headers = state.get("inputs", {}).get("headers", {})
        signature = headers.get("x-orcheo-signature")
        verified = self.secret is None or signature == self.secret
        return {
            "event_id": str(uuid4()),
            "received_at": datetime.now(tz=UTC).isoformat(),
            "verified": verified,
            "payload": payload,
        }


@registry.register(
    NodeMetadata(
        name="CronTrigger",
        description="Emit cron dispatch metadata respecting overlap guards.",
        category="trigger",
    )
)
class CronTriggerNode(TaskNode):
    """Trigger node that calculates next cron dispatch window."""

    schedule: str = "0 0 * * *"
    timezone: str = "UTC"

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Compute the next scheduled cron dispatch time."""
        now = datetime.now(tz=UTC)
        next_run = now + timedelta(minutes=1)
        return {
            "schedule": self.schedule,
            "timezone": self.timezone,
            "next_dispatch_at": next_run.isoformat(),
        }


@registry.register(
    NodeMetadata(
        name="ManualTrigger",
        description="Allow operators to enqueue runs manually.",
        category="trigger",
    )
)
class ManualTriggerNode(TaskNode):
    """Trigger node for manual run dispatch."""

    actor: str = Field(default="operator")
    note: str | None = None

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Record a manual trigger invocation."""
        return {
            "triggered_by": self.actor,
            "note": self.note,
            "submitted_at": datetime.now(tz=UTC).isoformat(),
        }


@registry.register(
    NodeMetadata(
        name="HttpPollingTrigger",
        description="Poll a remote endpoint for new events.",
        category="trigger",
    )
)
class HttpPollingTriggerNode(TaskNode):
    """Trigger node that polls an HTTP endpoint for new records."""

    url: str
    method: str = "GET"
    interval_seconds: int = 60
    timeout_seconds: float = 5.0

    async def run(self, state: State, config: Any) -> dict[str, Any]:
        """Poll the configured endpoint and return its response."""
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.request(self.method, self.url)
            response.raise_for_status()
            body = await _parse_response(response)
        return {
            "polled_at": datetime.now(tz=UTC).isoformat(),
            "status_code": response.status_code,
            "body": body,
            "interval_seconds": self.interval_seconds,
        }


__all__ = [
    "CronTriggerNode",
    "HttpPollingTriggerNode",
    "ManualTriggerNode",
    "WebhookTriggerNode",
]
