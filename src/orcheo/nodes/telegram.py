"""Telegram messaging node for Orcheo."""

import asyncio
from typing import Any
from langchain_core.runnables import RunnableConfig
from telegram import Bot
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


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
class MessageTelegram(TaskNode):
    """Node for sending Telegram messages."""

    token: str
    chat_id: str | None = None
    message: str | None = None
    parse_mode: str | None = None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Send message to Telegram and return status."""
        assert self.chat_id is not None
        assert self.message is not None
        return await self.tool_arun(self.chat_id, self.message, self.parse_mode)

    def tool_run(
        self, chat_id: str, message: str, parse_mode: str | None = None
    ) -> Any:
        """Send message to Telegram and return status.

        Args:
            chat_id: The ID of the chat to send the message to.
            message: The message to send.
            parse_mode: The parse mode to use for the message.
        """
        return asyncio.run(
            self.tool_arun(chat_id, message, parse_mode)
        )  # pragma: no cover

    async def tool_arun(
        self, chat_id: str, message: str, parse_mode: str | None = None
    ) -> dict:
        """Send message to Telegram and return status.

        Args:
            chat_id: The ID of the chat to send the message to.
            message: The message to send.
            parse_mode: The parse mode to use for the message.
        """
        bot = Bot(token=self.token)
        try:
            result = await bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            return {"message_id": result.message_id, "status": "sent"}
        except Exception as e:
            raise ValueError(f"Telegram API error: {str(e)}") from e
