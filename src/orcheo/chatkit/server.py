"""ChatKit server implementation backed by Orcheo services."""

from __future__ import annotations
import logging
from collections.abc import AsyncIterator, Iterable
from datetime import UTC, datetime
from uuid import UUID
from chatkit.server import ChatKitServer
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
from orcheo_backend.app.repository import WorkflowRepository
from .service import ChatTriggerService
from .store import InMemoryChatKitStore


LOGGER = logging.getLogger(__name__)


class OrcheoChatKitServer(ChatKitServer[dict[str, object]]):
    """ChatKit server that delegates chat messages to Orcheo workflows."""

    def __init__(self) -> None:
        """Initialise the ChatKit server with the in-memory store."""
        super().__init__(InMemoryChatKitStore())

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: dict[str, object],
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Respond to the incoming chat message by delegating to Orcheo."""
        if input_user_message is None:
            return

        message_text = self._extract_text(input_user_message.content)
        if not message_text:
            yield ThreadItemDoneEvent(
                item=self._build_assistant_message(
                    thread,
                    "I wasn't able to read any text in that message.",
                    context,
                )
            )
            return

        repository = self._resolve_repository(context)
        request = context.get("request")
        workflow_id = None
        node_id = None
        node_label = None

        if request is not None:
            headers = getattr(request, "headers", {})
            workflow_id = self._validated_uuid_header(
                headers.get("x-orcheo-chat-workflow-id"),
                header_name="x-orcheo-chat-workflow-id",
            )
            node_id = headers.get("x-orcheo-chat-node-id")
            node_label = headers.get("x-orcheo-chat-node-name")

        if repository is None:
            response = (
                "I received your message but couldn't reach the workflow repository. "
                "Try again once the server is fully initialised."
            )
        else:
            service = ChatTriggerService(repository)
            response = await service.handle_message(
                message_text,
                workflow_id=workflow_id,
                node_id=node_id,
                node_label=node_label,
            )

        yield ThreadItemDoneEvent(
            item=self._build_assistant_message(thread, response, context)
        )

    def _build_assistant_message(
        self,
        thread: ThreadMetadata,
        content: str,
        context: dict[str, object],
    ) -> AssistantMessageItem:
        return AssistantMessageItem(
            id=self.store.generate_item_id("message", thread, context),
            thread_id=thread.id,
            created_at=datetime.now(UTC),
            content=[AssistantMessageContent(text=content)],
        )

    @staticmethod
    def _extract_text(parts: Iterable[object]) -> str:
        texts: list[str] = []
        for part in parts:
            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
        return " ".join(texts).strip()

    @staticmethod
    def _resolve_repository(context: dict[str, object]) -> WorkflowRepository | None:
        repository = context.get("repository")
        if isinstance(repository, WorkflowRepository):
            return repository
        return None

    @staticmethod
    def _validated_uuid_header(value: object, *, header_name: str) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        candidate = value.strip()
        try:
            return str(UUID(candidate))
        except ValueError:
            LOGGER.warning(
                "Ignoring invalid UUID header",
                extra={"header": header_name, "value": candidate},
            )
            return None
