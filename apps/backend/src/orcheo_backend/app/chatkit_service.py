"""ChatKit server wiring for Orcheo workflows."""

from __future__ import annotations
import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypedDict
from uuid import UUID, uuid4
from chatkit.errors import CustomStreamError
from chatkit.server import ChatKitServer
from chatkit.store import Attachment, NotFoundError, Page, Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    Thread,
    ThreadItem,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageContent,
    UserMessageItem,
)
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
from orcheo.models import CredentialAccessContext
from orcheo.persistence import create_checkpointer
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.vault import BaseCredentialVault
from orcheo_backend.app.repository import (
    WorkflowRepository,
    WorkflowRun,
)


logger = logging.getLogger(__name__)


class ChatKitRequestContext(TypedDict, total=False):
    """Context passed to store operations and response handlers."""

    chatkit_request: BaseModel


@dataclass
class _ThreadState:
    """Internal storage for thread metadata and items."""

    thread: ThreadMetadata
    items: list[ThreadItem]


class InMemoryChatKitStore(Store[ChatKitRequestContext]):
    """Simple in-memory store retaining threads and items for ChatKit."""

    def __init__(self) -> None:
        """Initialise the backing storage structures."""
        self._threads: dict[str, _ThreadState] = {}
        self._lock = asyncio.Lock()

    # -- Helpers ---------------------------------------------------------
    @staticmethod
    def _clone_metadata(thread: ThreadMetadata | Thread) -> ThreadMetadata:
        """Return a metadata-only clone of the thread."""
        data = thread.model_dump()
        data.pop("items", None)
        return ThreadMetadata(**data)

    def _state_for(self, thread_id: str) -> _ThreadState:
        state = self._threads.get(thread_id)
        if state is None:
            state = _ThreadState(
                thread=ThreadMetadata(
                    id=thread_id,
                    created_at=datetime.now(UTC),
                ),
                items=[],
            )
            self._threads[thread_id] = state
        return state

    def _merge_metadata_from_context(
        self, thread: ThreadMetadata, context: ChatKitRequestContext
    ) -> None:
        metadata = getattr(context.get("chatkit_request"), "metadata", None)
        if not metadata:
            return
        merged = {**thread.metadata, **metadata}
        thread.metadata = merged

    # -- Thread metadata -------------------------------------------------
    async def load_thread(
        self, thread_id: str, context: ChatKitRequestContext
    ) -> ThreadMetadata:
        """Return stored metadata for ``thread_id`` or raise if missing."""
        async with self._lock:
            state = self._threads.get(thread_id)
            if state is None:
                raise NotFoundError(f"Thread {thread_id} not found")
            return self._clone_metadata(state.thread)

    async def save_thread(
        self, thread: ThreadMetadata, context: ChatKitRequestContext
    ) -> None:
        """Persist metadata for ``thread`` while merging incoming context metadata."""
        async with self._lock:
            self._merge_metadata_from_context(thread, context)
            existing = self._threads.get(thread.id)
            metadata = self._clone_metadata(thread)
            if existing:
                existing.thread = metadata
            else:
                self._threads[thread.id] = _ThreadState(thread=metadata, items=[])

    async def load_threads(
        self,
        limit: int,
        after: str | None,
        order: str,
        context: ChatKitRequestContext,
    ) -> Page[ThreadMetadata]:
        """Return a page of stored thread metadata ordered by creation."""
        async with self._lock:
            threads = sorted(
                (
                    self._clone_metadata(state.thread)
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
            return Page(
                data=slice_threads,
                has_more=has_more,
                after=next_after,
            )

    async def delete_thread(
        self, thread_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove the stored thread state if present."""
        async with self._lock:
            self._threads.pop(thread_id, None)

    # -- Thread items ----------------------------------------------------
    async def load_thread_items(
        self,
        thread_id: str,
        after: str | None,
        limit: int,
        order: str,
        context: ChatKitRequestContext,
    ) -> Page[ThreadItem]:
        """Return a page of thread items for ``thread_id``."""
        async with self._lock:
            state = self._state_for(thread_id)
            items = [item.model_copy(deep=True) for item in state.items]
            items.sort(
                key=lambda item: getattr(item, "created_at", datetime.now(UTC)),
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
        self, thread_id: str, item: ThreadItem, context: ChatKitRequestContext
    ) -> None:
        """Append ``item`` to the stored history for ``thread_id``."""
        async with self._lock:
            self._state_for(thread_id).items.append(item.model_copy(deep=True))

    async def save_item(
        self, thread_id: str, item: ThreadItem, context: ChatKitRequestContext
    ) -> None:
        """Insert or replace ``item`` in the stored history."""
        async with self._lock:
            items = self._state_for(thread_id).items
            for idx, existing in enumerate(items):
                if existing.id == item.id:
                    items[idx] = item.model_copy(deep=True)
                    return
            items.append(item.model_copy(deep=True))

    async def load_item(
        self, thread_id: str, item_id: str, context: ChatKitRequestContext
    ) -> ThreadItem:
        """Return a single stored item or raise if missing."""
        async with self._lock:
            for item in self._state_for(thread_id).items:
                if item.id == item_id:
                    return item.model_copy(deep=True)
        raise NotFoundError(f"Item {item_id} not found")

    async def delete_thread_item(
        self, thread_id: str, item_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove an item from the stored history if present."""
        async with self._lock:
            state = self._state_for(thread_id)
            state.items = [item for item in state.items if item.id != item_id]

    # -- Attachments -----------------------------------------------------
    async def save_attachment(
        self, attachment: Attachment, context: ChatKitRequestContext
    ) -> None:
        """Persist an attachment entry."""
        raise NotImplementedError(
            "Attachment upload is not supported. Provide a real store implementation "
            "before enabling file uploads."
        )

    async def load_attachment(
        self, attachment_id: str, context: ChatKitRequestContext
    ) -> Attachment:
        """Return a stored attachment or raise if unsupported."""
        raise NotImplementedError(
            "Attachments are not stored in the in-memory ChatKit store."
        )

    async def delete_attachment(
        self, attachment_id: str, context: ChatKitRequestContext
    ) -> None:
        """Remove a stored attachment."""
        raise NotImplementedError(
            "Attachments are not stored in the in-memory ChatKit store."
        )


def _collect_text_from_user_content(content: list[UserMessageContent]) -> str:
    parts: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            parts.append(str(text))
    return " ".join(parts).strip()


def _collect_text_from_assistant_content(
    content: list[AssistantMessageContent],
) -> str:
    parts: list[str] = []
    for item in content:
        if item.text:
            parts.append(str(item.text))
    return " ".join(parts).strip()


def _stringify_langchain_message(message: Any) -> str:
    value: Any
    if isinstance(message, BaseMessage):
        value = message.content
    elif isinstance(message, Mapping):
        value = message.get("content") or message.get("text")
    else:
        value = getattr(message, "content", message)

    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for entry in value:
            part = _stringify_langchain_message(entry)
            if part:
                parts.append(part)
        return " ".join(parts)
    return str(value)


def _build_initial_state(
    graph_config: Mapping[str, Any],
    inputs: Mapping[str, Any],
) -> Mapping[str, Any]:
    if graph_config.get("format") == LANGGRAPH_SCRIPT_FORMAT:
        return dict(inputs)
    return {
        "messages": [],
        "results": {},
        "inputs": dict(inputs),
    }


def _extract_reply_from_state(state: Mapping[str, Any]) -> str | None:
    if "reply" in state:
        reply = state["reply"]
        if reply is not None:
            return str(reply)

    results = state.get("results")
    if isinstance(results, Mapping):
        for value in results.values():
            if isinstance(value, Mapping) and "reply" in value:
                reply = value["reply"]
                if reply is not None:
                    return str(reply)
            if isinstance(value, str):
                return value

    messages = state.get("messages")
    if isinstance(messages, list) and messages:
        return _stringify_langchain_message(messages[-1])

    return None


class OrcheoChatKitServer(ChatKitServer[ChatKitRequestContext]):
    """ChatKit server streaming Orcheo workflow outputs back to the widget."""

    def __init__(
        self,
        store: Store[ChatKitRequestContext],
        repository: WorkflowRepository,
        vault_provider: Callable[[], BaseCredentialVault],
    ) -> None:
        """Initialise the ChatKit server with the configured repository."""
        super().__init__(store=store)
        self._repository = repository
        self._vault_provider = vault_provider

    async def _history(
        self, thread: ThreadMetadata, context: ChatKitRequestContext
    ) -> list[dict[str, str]]:
        history: list[dict[str, str]] = []
        page = await self.store.load_thread_items(
            thread.id,
            after=None,
            limit=200,
            order="asc",
            context=context,
        )
        for item in page.data:
            if isinstance(item, UserMessageItem):
                history.append(
                    {
                        "role": "user",
                        "content": _collect_text_from_user_content(item.content),
                    }
                )
            elif isinstance(item, AssistantMessageItem):
                history.append(
                    {
                        "role": "assistant",
                        "content": _collect_text_from_assistant_content(item.content),
                    }
                )
        return history

    @staticmethod
    def _require_workflow_id(thread: ThreadMetadata) -> UUID:
        """Return the workflow identifier stored on ``thread``."""
        workflow_value = thread.metadata.get("workflow_id")
        if not workflow_value:
            raise CustomStreamError(
                "No workflow has been associated with this conversation.",
                allow_retry=False,
            )
        try:
            return UUID(str(workflow_value))
        except ValueError as exc:
            raise CustomStreamError(
                "The configured workflow identifier is invalid.",
                allow_retry=False,
            ) from exc

    async def _resolve_user_item(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: ChatKitRequestContext,
    ) -> UserMessageItem:
        """Return the most recent user message for the thread."""
        if item is not None:
            return item

        page = await self.store.load_thread_items(
            thread.id, after=None, limit=1, order="desc", context=context
        )
        for candidate in page.data:
            if isinstance(candidate, UserMessageItem):
                return candidate

        raise CustomStreamError(
            "Unable to locate the user message for this request.",
            allow_retry=False,
        )

    @staticmethod
    def _build_inputs_payload(
        thread: ThreadMetadata, message_text: str, history: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Construct the workflow input payload."""
        return {
            "message": message_text,
            "history": history,
            "thread_id": thread.id,
            "metadata": dict(thread.metadata),
        }

    @staticmethod
    def _record_run_metadata(thread: ThreadMetadata, run: WorkflowRun | None) -> None:
        """Persist run identifiers on the thread metadata."""
        thread.metadata = {
            **thread.metadata,
            "last_run_at": datetime.now(UTC).isoformat(),
        }
        if "runs" in thread.metadata and isinstance(thread.metadata["runs"], list):
            runs_list = list(thread.metadata["runs"])
        else:
            runs_list = []

        if run is not None:
            runs_list.append(str(run.id))
            thread.metadata["last_run_id"] = str(run.id)

        if runs_list:
            thread.metadata["runs"] = runs_list[-20:]

    def _build_assistant_item(
        self,
        thread: ThreadMetadata,
        reply: str,
        context: ChatKitRequestContext,
    ) -> AssistantMessageItem:
        """Create a ChatKit assistant message item from the reply text."""
        return AssistantMessageItem(
            id=self.store.generate_item_id("message", thread, context),
            thread_id=thread.id,
            created_at=datetime.now(UTC),
            content=[AssistantMessageContent(text=reply)],
        )

    async def _run_workflow(
        self,
        workflow_id: UUID,
        inputs: Mapping[str, Any],
        *,
        actor: str = "chatkit",
    ) -> tuple[str, Mapping[str, Any], WorkflowRun | None]:
        version = await self._repository.get_latest_version(workflow_id)

        run: WorkflowRun | None = None
        try:
            run = await self._repository.create_run(
                workflow_id,
                workflow_version_id=version.id,
                triggered_by=actor,
                input_payload=dict(inputs),
            )
            await self._repository.mark_run_started(run.id, actor=actor)
        except Exception:  # pragma: no cover - repository failure
            logger.exception("Failed to record workflow run metadata")

        graph_config = version.graph
        settings = get_settings()
        vault = self._vault_provider()
        credential_context = CredentialAccessContext(workflow_id=workflow_id)
        credential_resolver = CredentialResolver(vault, context=credential_context)

        async with create_checkpointer(settings) as checkpointer:
            graph = build_graph(graph_config)
            compiled = graph.compile(checkpointer=checkpointer)
            initial_state = _build_initial_state(graph_config, inputs)
            payload: Any = initial_state
            config: RunnableConfig = {
                "configurable": {"thread_id": str(uuid4())},
            }
            with credential_resolution(credential_resolver):
                final_state = await compiled.ainvoke(payload, config=config)

        if isinstance(final_state, BaseModel):
            state_view: Mapping[str, Any] = final_state.model_dump()
        elif isinstance(final_state, Mapping):
            state_view = final_state
        else:  # pragma: no cover - defensive
            state_view = dict(final_state or {})

        reply = _extract_reply_from_state(state_view)
        if reply is None:
            raise CustomStreamError(
                "Workflow completed without producing a reply.",
                allow_retry=False,
            )

        try:
            if run is not None:
                await self._repository.mark_run_succeeded(
                    run.id,
                    actor=actor,
                    output={"reply": reply},
                )
        except Exception:  # pragma: no cover - repository failure
            logger.exception("Failed to mark workflow run succeeded")

        return reply, state_view, run

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: ChatKitRequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Execute the workflow and yield assistant events."""
        # workflow_id = self._require_workflow_id(thread)
        # user_item = await self._resolve_user_item(thread, item, context)
        # message_text = _collect_text_from_user_content(user_item.content)
        # history = await self._history(thread, context)
        # inputs = self._build_inputs_payload(thread, message_text, history)

        # try:
        #     reply, _state, run = await self._run_workflow(workflow_id, inputs)
        # except WorkflowNotFoundError as exc:
        #     raise CustomStreamError(str(exc), allow_retry=False) from exc
        # except WorkflowVersionNotFoundError as exc:
        #     raise CustomStreamError(str(exc), allow_retry=False) from exc

        # self._record_run_metadata(thread, run)
        reply = "Hello, world!"
        assistant_item = self._build_assistant_item(thread, reply, context)
        yield ThreadItemDoneEvent(item=assistant_item)


def create_chatkit_server(
    repository: WorkflowRepository,
    vault_provider: Callable[[], BaseCredentialVault],
) -> OrcheoChatKitServer:
    """Factory returning an Orcheo-configured ChatKit server."""
    store = InMemoryChatKitStore()
    return OrcheoChatKitServer(
        store=store,
        repository=repository,
        vault_provider=vault_provider,
    )
