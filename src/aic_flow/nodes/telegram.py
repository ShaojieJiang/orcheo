"""Telegram messaging node for AIC Flow."""

from dataclasses import dataclass
from typing import Any
import telegram
from aic_flow.graph.state import State
from aic_flow.nodes.base import BaseNode
from aic_flow.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="TelegramMessage",
        description="Send message to Telegram",
        input_schema={
            "type": "object",
            "properties": {
                "token": {"type": "string", "description": "Telegram bot token"},
                "chat_id": {
                    "type": "string",
                    "description": "Chat ID to send message to",
                },
                "message": {"type": "string", "description": "Message to send"},
            },
            "required": ["token", "chat_id", "message"],
        },
        output_schema={
            "type": "object",
            "description": "Message status",
        },
        category="messaging",
    )
)
@dataclass
class TelegramNode(BaseNode):
    """Node for sending Telegram messages."""

    token: str
    chat_id: str
    message: str

    async def run(self, state: State) -> dict[str, Any]:
        """Send message to Telegram and return status."""
        bot = telegram.Bot(token=self.token)
        result = await bot.send_message(chat_id=self.chat_id, text=self.message)
        return {"message_id": result.message_id, "status": "sent"}
