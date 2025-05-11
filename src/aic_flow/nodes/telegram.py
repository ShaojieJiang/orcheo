"""Telegram messaging node for AIC Flow."""

from dataclasses import dataclass
from typing import Any
import httpx
from langchain_core.runnables import RunnableConfig
from aic_flow.graph.state import State
from aic_flow.nodes.base import TaskNode
from aic_flow.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="MessageTelegram",
        description="Send message to Telegram",
        category="messaging",
    )
)
@dataclass
class MessageTelegram(TaskNode):
    """Node for sending Telegram messages."""

    token: str
    chat_id: str
    message: str

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Send message to Telegram and return status."""
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": self.message,
            "parse_mode": "MarkdownV2",
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            result = response.json()
            return {"message_id": result["result"]["message_id"], "status": "sent"}
