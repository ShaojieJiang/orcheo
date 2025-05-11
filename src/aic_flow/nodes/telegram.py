"""Telegram messaging node for AIC Flow."""

import asyncio
from dataclasses import dataclass
from typing import Any
import telegram
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

    def run(self, state: State) -> dict[str, Any]:
        """Send message to Telegram and return status."""
        bot = telegram.Bot(token=self.token)
        result = asyncio.run(bot.send_message(chat_id=self.chat_id, text=self.message))
        return {"message_id": result.message_id, "status": "sent"}
