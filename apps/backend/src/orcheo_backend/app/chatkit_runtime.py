# ruff: noqa: D102, D107

from __future__ import annotations
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from chatkit.server import (
    ChatKitServer,
    NonStreamingResult,
    StreamingResult,
    ThreadItemDoneEvent,
)
from chatkit.store import NotFoundError, Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    Page,
    Thread,
    ThreadItem,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
from orcheo.models.workflow import Workflow, WorkflowRun
from orcheo.triggers.manual import (
    ManualDispatchItem,
    ManualDispatchRequest,
    ManualDispatchValidationError,
)
from orcheo.vault.oauth import CredentialHealthError
from .repository import (
    WorkflowRepository,
    WorkflowVersionNotFoundError,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChatRequestContext:
    """Runtime context for ChatKit requests."""

    repository: WorkflowRepository
    workflow: Workflow
    node_id: str | None
    actor: str
    chat_label: str | None


@dataclass(slots=True)
class _ThreadState:
    thread: ThreadMetadata
    items: list[ThreadItem]


class InMemoryChatStore(Store[ChatRequestContext]):
    """Simple in-memory store compatible with the ChatKit server interface."""

    def __init__(self) -> None:
        self._threads: dict[str, _ThreadState] = {}

    @staticmethod
    def _coerce_thread_metadata(thread: ThreadMetadata | Thread) -> ThreadMetadata:
        has_items = isinstance(thread, Thread) or "items" in getattr(
            thread,
            "model_fields_set",
            set(),
        )
        if not has_items:
            return thread.model_copy(deep=True)

        data = thread.model_dump()
        data.pop("items", None)
        return ThreadMetadata(**data).model_copy(deep=True)

    async def load_thread(
        self, thread_id: str, context: ChatRequestContext
    ) -> ThreadMetadata:
        state = self._threads.get(thread_id)
        if not state:
            raise NotFoundError(f"Thread {thread_id} not found")
        return self._coerce_thread_metadata(state.thread)

    async def save_thread(
        self, thread: ThreadMetadata, context: ChatRequestContext
    ) -> None:
        metadata = self._coerce_thread_metadata(thread)
        state = self._threads.get(thread.id)
        if state:
            state.thread = metadata
        else:
            self._threads[thread.id] = _ThreadState(thread=metadata, items=[])

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: ChatRequestContext,
    ) -> Page[ThreadMetadata]:
        threads = sorted(
            (
                self._coerce_thread_metadata(state.thread)
                for state in self._threads.values()
            ),
            key=lambda t: t.created_at or datetime.min,
            reverse=(order == "desc"),
        )

        if after:
            index_map = {thread.id: idx for idx, thread in enumerate(threads)}
            start = index_map.get(after, -1) + 1
        else:
            start = 0

        slice_threads = threads[start : start + limit + 1]
        has_more = len(slice_threads) > limit
        slice_threads = slice_threads[:limit]
        next_after = slice_threads[-1].id if has_more and slice_threads else None
        return Page(data=slice_threads, has_more=has_more, after=next_after)

    async def delete_thread(self, thread_id: str, context: ChatRequestContext) -> None:
        self._threads.pop(thread_id, None)

    def _items(self, thread_id: str) -> list[ThreadItem]:
        state = self._threads.get(thread_id)
        if state is None:
            state = _ThreadState(
                thread=ThreadMetadata(id=thread_id, created_at=datetime.utcnow()),
                items=[],
            )
            self._threads[thread_id] = state
        return state.items

    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: ChatRequestContext,
    ) -> Page[ThreadItem]:
        items = [item.model_copy(deep=True) for item in self._items(thread_id)]
        items.sort(
            key=lambda item: getattr(item, "created_at", datetime.utcnow()),
            reverse=(order == "desc"),
        )

        if after:
            index_map = {item.id: idx for idx, item in enumerate(items)}
            start = index_map.get(after, -1) + 1
        else:
            start = 0

        slice_items = items[start : start + limit + 1]
        has_more = len(slice_items) > limit
        slice_items = slice_items[:limit]
        next_after = slice_items[-1].id if has_more and slice_items else None
        return Page(data=slice_items, has_more=has_more, after=next_after)

    async def add_thread_item(
        self,
        thread_id: str,
        item: ThreadItem,
        context: ChatRequestContext,
    ) -> None:
        self._items(thread_id).append(item.model_copy(deep=True))

    async def save_item(
        self,
        thread_id: str,
        item: ThreadItem,
        context: ChatRequestContext,
    ) -> None:
        items = self._items(thread_id)
        for idx, existing in enumerate(items):
            if existing.id == item.id:
                items[idx] = item.model_copy(deep=True)
                return
        items.append(item.model_copy(deep=True))

    async def load_item(
        self,
        thread_id: str,
        item_id: str,
        context: ChatRequestContext,
    ) -> ThreadItem:
        for item in self._items(thread_id):
            if item.id == item_id:
                return item.model_copy(deep=True)
        raise NotFoundError(f"Item {item_id} not found")

    async def delete_thread_item(
        self,
        thread_id: str,
        item_id: str,
        context: ChatRequestContext,
    ) -> None:
        """Remove a thread item from the in-memory store."""
        items = self._items(thread_id)
        self._threads[thread_id].items = [item for item in items if item.id != item_id]

    async def save_attachment(
        self,
        attachment: Any,
        context: ChatRequestContext,
    ) -> None:
        """Attachments are unsupported in the in-memory store."""
        raise NotImplementedError("InMemoryChatStore does not persist attachments.")

    async def load_attachment(
        self,
        attachment_id: str,
        context: ChatRequestContext,
    ) -> Any:
        """Attachments are unsupported in the in-memory store."""
        raise NotImplementedError("InMemoryChatStore does not load attachments.")

    async def delete_attachment(
        self,
        attachment_id: str,
        context: ChatRequestContext,
    ) -> None:
        """Attachments are unsupported in the in-memory store."""
        raise NotImplementedError("InMemoryChatStore does not delete attachments.")


class WorkflowChatKitServer(ChatKitServer[ChatRequestContext]):
    """ChatKit server that dispatches Orcheo workflows for chat triggers."""

    def __init__(self, store: Store[ChatRequestContext]) -> None:
        """Initialise the chat server with the provided persistence store."""
        super().__init__(store)

    async def respond(
        self,
        thread: ThreadMetadata,
        input_user_message: UserMessageItem | None,
        context: ChatRequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Process a user message and stream workflow execution events."""
        if input_user_message is None:
            return

        self._ensure_thread_metadata(thread, context)
        message_text = self._extract_message_text(input_user_message)
        if not message_text:
            yield self._build_assistant_event(
                thread,
                context,
                "I didn't receive any text. Try sending a message again.",
            )
            return

        summary = await self._dispatch_workflow(thread, context, message_text)
        yield self._build_assistant_event(thread, context, summary)

    async def _dispatch_workflow(
        self,
        thread: ThreadMetadata,
        context: ChatRequestContext,
        message_text: str,
    ) -> str:
        label = context.chat_label or (
            f"chat:{context.node_id}" if context.node_id else "chatkit"
        )

        request = ManualDispatchRequest(
            workflow_id=context.workflow.id,
            actor=context.actor,
            label=label,
            runs=[
                ManualDispatchItem(
                    input_payload={
                        "chat_message": message_text,
                        "chat_thread_id": thread.id,
                        "chat_node_id": context.node_id,
                    },
                )
            ],
        )

        try:
            runs = await context.repository.dispatch_manual_runs(request)
        except WorkflowVersionNotFoundError as exc:  # pragma: no cover - defensive
            logger.exception(
                "Workflow version not found for chat dispatch",
                exc_info=exc,
            )
            return (
                "The workflow does not have an active version. "
                "Publish a version and try again."
            )
        except CredentialHealthError as exc:
            logger.warning(
                "Credential health check failed for chat dispatch",
                exc_info=exc,
            )
            return f"Workflow could not start due to credential health issues: {exc}"
        except ManualDispatchValidationError as exc:
            logger.warning("Invalid chat dispatch payload", exc_info=exc)
            return f"Unable to dispatch the workflow: {exc}"
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected error while dispatching chat workflow")
            return (
                "An unexpected error prevented the workflow from running. "
                "Check the server logs for more details."
            )

        if not runs:
            return "No workflow runs were created for this message."

        run = runs[0]
        return self._format_run_summary(run, context, message_text)

    def _format_run_summary(
        self,
        run: WorkflowRun,
        context: ChatRequestContext,
        message_text: str,
    ) -> str:
        snippet = message_text.strip()
        if len(snippet) > 120:
            snippet = snippet[:117] + "…"

        parts = [
            f"Triggered run {run.id} for “{context.workflow.name}”.",
            f"Current status: {run.status.value}.",
        ]
        if snippet:
            parts.append(f'Input: "{snippet}"')
        parts.append("Follow the execution history for live updates.")
        return " ".join(parts)

    def _ensure_thread_metadata(
        self,
        thread: ThreadMetadata,
        context: ChatRequestContext,
    ) -> None:
        metadata = dict(thread.metadata or {})
        updated = False
        if metadata.get("workflow_id") != str(context.workflow.id):
            metadata["workflow_id"] = str(context.workflow.id)
            updated = True
        if (
            context.workflow.name
            and metadata.get("workflow_name") != context.workflow.name
        ):
            metadata["workflow_name"] = context.workflow.name
            updated = True
        if context.node_id and metadata.get("node_id") != context.node_id:
            metadata["node_id"] = context.node_id
            updated = True
        if updated:
            thread.metadata = metadata

    def _extract_message_text(self, item: UserMessageItem) -> str:
        parts: list[str] = []
        for content in item.content:
            text = getattr(content, "text", None)
            if text:
                parts.append(text)
        return " ".join(parts).strip()

    def _build_assistant_event(
        self,
        thread: ThreadMetadata,
        context: ChatRequestContext,
        message: str,
    ) -> ThreadItemDoneEvent:
        item = AssistantMessageItem(
            id=self.store.generate_item_id("message", thread, context),
            thread_id=thread.id,
            created_at=datetime.utcnow(),
            content=[AssistantMessageContent(text=message, annotations=[])],
        )
        return ThreadItemDoneEvent(item=item)


def create_chatkit_server() -> WorkflowChatKitServer:
    """Instantiate the ChatKit server with an in-memory store."""
    store = InMemoryChatStore()
    return WorkflowChatKitServer(store)


__all__ = [
    "ChatRequestContext",
    "InMemoryChatStore",
    "WorkflowChatKitServer",
    "create_chatkit_server",
    "NonStreamingResult",
    "StreamingResult",
]
