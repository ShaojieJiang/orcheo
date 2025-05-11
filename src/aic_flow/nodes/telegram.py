"""Telegram messaging node for AIC Flow."""

from dataclasses import dataclass
from typing import Any
import telegram
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
        bot = telegram.Bot(token=self.token)
        result = await bot.send_message(chat_id=self.chat_id, text=self.message)
        return {"message_id": result.message_id, "status": "sent"}
