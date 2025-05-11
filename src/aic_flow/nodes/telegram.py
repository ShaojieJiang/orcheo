"""Telegram messaging node for AIC Flow."""

from dataclasses import dataclass
from typing import Any
from langchain_core.runnables import RunnableConfig
from telegram import Bot
from aic_flow.graph.state import State
from aic_flow.nodes.base import TaskNode
from aic_flow.nodes.registry import NodeMetadata, registry


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]
    escaped_text = ""
    for char in text:
        if char in special_chars:
            escaped_text += f"\\{char}"
        else:
            escaped_text += char
    return escaped_text


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
    parse_mode: str | None = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Send message to Telegram and return status."""
        bot = Bot(token=self.token)
        try:
            result = await bot.send_message(
                chat_id=self.chat_id,
                text=self.message,
                parse_mode=self.parse_mode,
            )
            return {"message_id": result.message_id, "status": "sent"}
        except Exception as e:
            raise ValueError(f"Telegram API error: {str(e)}") from e
