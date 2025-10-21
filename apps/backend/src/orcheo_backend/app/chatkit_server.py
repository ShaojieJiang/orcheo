from __future__ import annotations
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from chatkit.server import ChatKitServer, ThreadItemDoneEvent
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
from .chatkit_store import MemoryStore


def _extract_user_text(message: UserMessageItem | None) -> str:
    if message is None:
        return ""

    parts: list[str] = []
    for content in message.content:
        text = getattr(content, "text", None)
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())

    return " ".join(parts).strip()


def _generate_response(prompt: str) -> str:
    normalized = prompt.lower()
    if not normalized:
        return (
            "Thanks for opening the chat! Send a message to trigger the workflow "
            "and see how it responds."
        )

    if "hello" in normalized or "hi" in normalized:
        return "Hello there! Ready to kick off your Orcheo workflow tests?"

    if "workflow" in normalized:
        return (
            "This chat trigger will capture your message as workflow input. "
            "Update the workflow run to inspect how nodes react."
        )

    if "help" in normalized:
        return (
            "Try describing the scenario you'd like to simulate. I'll confirm the "
            "workflow run so you can inspect it in the canvas."
        )

    return (
        "Got it! I've recorded your message so the workflow can process it. "
        "Check the execution panel to follow the run."
    )


class OrcheoChatKitServer(ChatKitServer[dict[str, Any]]):
    """Lightweight ChatKit server that echoes guidance for workflow tests."""

    def __init__(self) -> None:
        """Initialize the server with an in-memory store."""
        super().__init__(MemoryStore())

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, Any],
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Stream a simple assistant message acknowledging the user's input."""
        prompt = _extract_user_text(input_user_message)
        reply_text = _generate_response(prompt)
        item = AssistantMessageItem(
            id=self.store.generate_item_id("message", thread, context),
            thread_id=thread.id,
            created_at=datetime.now(UTC),
            content=[AssistantMessageContent(text=reply_text)],
        )
        yield ThreadItemDoneEvent(item=item)
