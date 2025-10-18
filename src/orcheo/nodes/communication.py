"""Communication nodes for messaging integrations."""

from __future__ import annotations
from typing import Any
import httpx as _httpx
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


class _HttpxNamespace:
    """Container exposing httpx client classes for easy monkeypatching."""

    AsyncClient = _httpx.AsyncClient


httpx = _HttpxNamespace()


@registry.register(
    NodeMetadata(
        name="EmailNotification",
        description="Compose an email notification payload.",
        category="communication",
    )
)
class EmailNotification(TaskNode):
    """Create an email payload suitable for downstream delivery."""

    to: list[str]
    subject: str
    body: str
    from_address: str = Field(default="no-reply@orcheo.local")

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Return a structured payload representing the email."""
        return {
            "from": self.from_address,
            "to": list(self.to),
            "subject": self.subject,
            "body": self.body,
        }


class DiscordEmbed(BaseModel):
    """Minimal representation of a Discord embed payload."""

    title: str
    description: str


@registry.register(
    NodeMetadata(
        name="DiscordMessage",
        description="Send a Discord webhook message.",
        category="communication",
    )
)
class DiscordMessage(TaskNode):
    """Send or preview a Discord webhook message."""

    webhook_url: str
    content: str
    embeds: list[DiscordEmbed] = Field(default_factory=list)
    send: bool = False

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Optionally send the Discord webhook and return the payload."""
        payload = {
            "content": self.content,
            "embeds": [embed.model_dump() for embed in self.embeds],
        }
        if self.send:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                try:
                    response.raise_for_status()
                except RuntimeError:
                    if response.is_error:
                        msg = (
                            "Discord webhook request failed: "
                            f"status={response.status_code}"
                        )
                        raise RuntimeError(msg) from None
        return payload


__all__ = ["EmailNotification", "DiscordMessage", "DiscordEmbed"]
