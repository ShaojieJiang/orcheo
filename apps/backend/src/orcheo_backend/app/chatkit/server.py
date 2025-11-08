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
from orcheo.vault import BaseCredentialVault
from orcheo_backend.app.chatkit.context import ChatKitRequestContext
from orcheo_backend.app.chatkit.legacy_support import (
    call_build_graph,
    call_get_settings,
)
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


def _call_get_settings() -> Any:
    """Proxy for legacy settings helper so tests can monkeypatch this module."""
    return call_get_settings()


def _call_build_graph(graph_config: Mapping[str, Any]) -> Any:
    """Proxy for legacy graph builder to keep backwards-compat imports working."""
    return call_build_graph(graph_config)


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
        """Compatibility wrapper delegating to the history helper."""
        return await build_history(self.store, thread, context)

    @staticmethod
    def _require_workflow_id(thread: ThreadMetadata) -> UUID:
        """Compatibility wrapper delegating to the workflow id helper."""
        return require_workflow_id(thread)

    async def _resolve_user_item(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: ChatKitRequestContext,
    ) -> UserMessageItem:
        """Compatibility wrapper delegating to the user item helper."""
        return await resolve_user_item(self.store, thread, item, context)

    @staticmethod
    def _build_inputs_payload(
        thread: ThreadMetadata, message_text: str, history: list[dict[str, str]]
    ) -> dict[str, Any]:
        """Compatibility wrapper delegating to the payload helper."""
        return build_inputs_payload(thread, message_text, history)

    @staticmethod
    def _record_run_metadata(thread: ThreadMetadata, run: WorkflowRun | None) -> None:
        """Compatibility wrapper delegating to the metadata helper."""
        record_run_metadata(thread, run)

    def _build_assistant_item(
        self,
        thread: ThreadMetadata,
        reply: str,
        context: ChatKitRequestContext,
    ) -> AssistantMessageItem:
        """Compatibility wrapper delegating to the assistant item helper."""
        return build_assistant_item(self.store, thread, reply, context)

    async def _run_workflow(
        self,
        workflow_id: UUID,
        inputs: Mapping[str, Any],
        *,
        actor: str = "chatkit",
    ) -> tuple[str, Mapping[str, Any], WorkflowRun | None]:
        """Compatibility wrapper delegating to the workflow executor."""
        return await self._workflow_executor.run(workflow_id, inputs, actor=actor)

    async def respond(
        self,
        thread: ThreadMetadata,
        item: UserMessageItem | None,
        context: ChatKitRequestContext,
    ) -> AsyncIterator[ThreadStreamEvent]:
        """Execute the workflow and yield assistant events."""
        workflow_id = self._require_workflow_id(thread)
        user_item = await self._resolve_user_item(thread, item, context)
        message_text = collect_text_from_user_content(user_item.content)
        history = await self._history(thread, context)
        inputs = self._build_inputs_payload(thread, message_text, history)

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


def create_chatkit_server(
    repository: WorkflowRepository,
    vault_provider: Callable[[], BaseCredentialVault],
    *,
    store: Store[ChatKitRequestContext] | None = None,
) -> OrcheoChatKitServer:
    """Factory returning an Orcheo-configured ChatKit server."""
    if store is None:
        settings = _call_get_settings()
        candidate = settings.get(
            "CHATKIT_SQLITE_PATH",
            getattr(settings, "chatkit_sqlite_path", "~/.orcheo/chatkit.sqlite"),
        )
        sqlite_path = Path(str(candidate or "~/.orcheo/chatkit.sqlite")).expanduser()
        store = SqliteChatKitStore(sqlite_path)
    return OrcheoChatKitServer(
        store=store,
        repository=repository,
        vault_provider=vault_provider,
    )


__all__ = ["OrcheoChatKitServer", "create_chatkit_server"]
