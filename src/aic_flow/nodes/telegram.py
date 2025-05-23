"""Telegram messaging node for AIC Flow."""

import asyncio
from dataclasses import dataclass
from typing import Any
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
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


class MessageTelegramSchema(BaseModel):
    """Schema for MessageTelegram tool."""

    chat_id: str = Field(..., description="The ID of the chat to send the message to.")
    message: str = Field(..., description="The message to send.")
    parse_mode: str | None = Field(
        None, description="The parse mode to use for the message."
    )


@registry.register(
    NodeMetadata(
        name="MessageTelegram",
        description="Send message to Telegram",
        category="messaging",
    )
)
class MessageTelegram(TaskNode, BaseTool):
    """Node for sending Telegram messages."""

    token: str
    args_schema = MessageTelegramSchema
    chat_id: str | None = None
    message: str | None = None
    parse_mode: str | None = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Send message to Telegram and return status."""
        return self.tool_run(self.chat_id, self.message, self.parse_mode)

    def _run(self, chat_id: str, message: str, parse_mode: str | None = None) -> dict:
        """Send message to Telegram and return status."""
        bot = Bot(token=self.token)
        try:
            result = asyncio.run(
                bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode,
                )
            )
            return {"message_id": result.message_id, "status": "sent"}
        except Exception as e:
            raise ValueError(f"Telegram API error: {str(e)}") from e
