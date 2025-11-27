"""ChatKit server implementation streaming Orcheo workflow results."""

from __future__ import annotations
from collections.abc import AsyncIterator, Callable, Mapping
from pathlib import Path
from typing import Any
from uuid import UUID
from chatkit.errors import CustomStreamError
from chatkit.server import ChatKitServer
from chatkit.store import Store
from chatkit.types import (
    AssistantMessageItem,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
from dynaconf import Dynaconf
from orcheo.config import get_settings
from orcheo.vault import BaseCredentialVault
from orcheo_backend.app.chatkit.context import ChatKitRequestContext
from orcheo_backend.app.chatkit.message_utils import collect_text_from_user_content
from orcheo_backend.app.chatkit.messages import (
    build_assistant_item,
    build_history,
    build_inputs_payload,
    record_run_metadata,
    require_workflow_id,
    resolve_user_item,
)
from orcheo_backend.app.chatkit.workflow_executor import WorkflowExecutor
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowRepository,
    WorkflowRun,
    WorkflowVersionNotFoundError,
)


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
        self._workflow_executor = WorkflowExecutor(
            repository=repository, vault_provider=vault_provider
        )

    async def _history(
        self, thread: ThreadMetadata, context: ChatKitRequestContext
    ) -> list[dict[str, str]]:
        """Delegate to the shared history helper."""
        return await build_history(self.store, thread, context)

    @staticmethod
    def _require_workflow_id(thread: ThreadMetadata) -> UUID:
        """Delegate to the workflow id helper."""
        return require_workflow_id(thread)

    @staticmethod
    def _ensure_workflow_metadata(
        thread: ThreadMetadata, context: ChatKitRequestContext
    ) -> None:
        """Populate workflow metadata from request context when missing."""
        metadata = dict(thread.metadata or {})
        if metadata.get("workflow_id"):
            thread.metadata = metadata
            return
        context_workflow_id = context.get("workflow_id") if context else None
        if context_workflow_id:
            metadata["workflow_id"] = context_workflow_id
            thread.metadata = metadata

    async def _resolve_user_item(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: ChatKitRequestContext,
    ) -> UserMessageItem:
        """Delegate to the user item helper."""
        return await resolve_user_item(self.store, thread, item, context)

    @staticmethod
    def _build_inputs_payload(
        thread: ThreadMetadata,
        message_text: str,
        history: list[dict[str, str]],
        user_item: UserMessageItem | None = None,
    ) -> dict[str, Any]:
        """Delegate to the payload helper."""
        return build_inputs_payload(thread, message_text, history, user_item)

    @staticmethod
    def _record_run_metadata(thread: ThreadMetadata, run: WorkflowRun | None) -> None:
        """Delegate to the metadata helper."""
        record_run_metadata(thread, run)

    def _build_assistant_item(
        self,
        thread: ThreadMetadata,
        reply: str,
        context: ChatKitRequestContext,
    ) -> AssistantMessageItem:
        """Delegate to the assistant item helper."""
        return build_assistant_item(self.store, thread, reply, context)

    async def _run_workflow(
        self,
        workflow_id: UUID,
        inputs: Mapping[str, Any],
        *,
        actor: str = "chatkit",
    ) -> tuple[str, Mapping[str, Any], WorkflowRun | None]:
        """Delegate execution to the workflow executor."""
        return await self._workflow_executor.run(workflow_id, inputs, actor=actor)

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: ChatKitRequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Execute the workflow and yield assistant events."""
        self._ensure_workflow_metadata(thread, context)
        workflow_id = self._require_workflow_id(thread)
        user_item = await self._resolve_user_item(thread, item, context)
        message_text = collect_text_from_user_content(user_item.content)
        history = await self._history(thread, context)
        inputs = self._build_inputs_payload(thread, message_text, history, user_item)

        actor = str(context.get("actor") or "chatkit")
        try:
            reply, _state, run = await self._run_workflow(
                workflow_id, inputs, actor=actor
            )
        except WorkflowNotFoundError as exc:
            raise CustomStreamError(str(exc), allow_retry=False) from exc
        except WorkflowVersionNotFoundError as exc:
            raise CustomStreamError(str(exc), allow_retry=False) from exc

        self._record_run_metadata(thread, run)
        assistant_item = self._build_assistant_item(thread, reply, context)
        await self.store.add_thread_item(thread.id, assistant_item, context)
        await self.store.save_thread(thread, context)
        yield ThreadItemDoneEvent(item=assistant_item)


def _resolve_chatkit_sqlite_path(settings: Any) -> Path:
    """Return the configured ChatKit SQLite path with a consistent strategy."""
    default_path = Path("~/.orcheo/chatkit.sqlite")
    candidate: Any | None = None

    if isinstance(settings, Dynaconf):
        candidate = settings.get("CHATKIT_SQLITE_PATH")
    elif isinstance(settings, Mapping):
        candidate = settings.get("CHATKIT_SQLITE_PATH")
    else:
        candidate = getattr(settings, "chatkit_sqlite_path", None)
        if candidate is None:
            candidate = getattr(settings, "CHATKIT_SQLITE_PATH", None)

    if not candidate:
        return default_path.expanduser()

    return Path(str(candidate)).expanduser()


def create_chatkit_server(
    repository: WorkflowRepository,
    vault_provider: Callable[[], BaseCredentialVault],
    *,
    store: Store[ChatKitRequestContext] | None = None,
) -> OrcheoChatKitServer:
    """Factory returning an Orcheo-configured ChatKit server."""
    if store is None:
        settings = get_settings()
        sqlite_path = _resolve_chatkit_sqlite_path(settings)
        store = SqliteChatKitStore(sqlite_path)
    return OrcheoChatKitServer(
        store=store,
        repository=repository,
        vault_provider=vault_provider,
    )


__all__ = ["OrcheoChatKitServer", "create_chatkit_server"]
