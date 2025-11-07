"""ChatKit server implementation streaming Orcheo workflow results."""

from __future__ import annotations
import logging
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4
from chatkit.errors import CustomStreamError
from chatkit.server import ChatKitServer
from chatkit.store import Store
from chatkit.types import (
    AssistantMessageContent,
    AssistantMessageItem,
    ThreadItemDoneEvent,
    ThreadMetadata,
    ThreadStreamEvent,
    UserMessageItem,
)
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.models import CredentialAccessContext
from orcheo.persistence import create_checkpointer
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.vault import BaseCredentialVault
from orcheo_backend.app.chatkit.context import ChatKitRequestContext
from orcheo_backend.app.chatkit.message_utils import (
    build_initial_state,
    collect_text_from_assistant_content,
    collect_text_from_user_content,
    extract_reply_from_state,
)
from orcheo_backend.app.chatkit_store_sqlite import SqliteChatKitStore
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowRepository,
    WorkflowRun,
    WorkflowVersionNotFoundError,
)


logger = logging.getLogger(__name__)


def _legacy_module() -> ModuleType:
    """Return the compatibility module for legacy ChatKit imports."""
    return import_module("orcheo_backend.app.chatkit_service")


def _call_get_settings() -> Any:
    """Retrieve settings via the legacy module so tests can patch it."""
    return _legacy_module().get_settings()


def _call_build_graph(graph_config: Mapping[str, Any]) -> Any:
    """Build a graph via the legacy module to keep patch hooks working."""
    return _legacy_module().build_graph(graph_config)


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
                        "content": collect_text_from_user_content(item.content),
                    }
                )
            elif isinstance(item, AssistantMessageItem):
                history.append(
                    {
                        "role": "assistant",
                        "content": collect_text_from_assistant_content(item.content),
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
        settings = _call_get_settings()
        vault = self._vault_provider()
        credential_context = CredentialAccessContext(workflow_id=workflow_id)
        credential_resolver = CredentialResolver(vault, context=credential_context)

        async with create_checkpointer(settings) as checkpointer:
            graph = _call_build_graph(graph_config)
            compiled = graph.compile(checkpointer=checkpointer)
            initial_state = build_initial_state(graph_config, inputs)
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

        reply = extract_reply_from_state(state_view)
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
        workflow_id = self._require_workflow_id(thread)
        user_item = await self._resolve_user_item(thread, item, context)
        message_text = collect_text_from_user_content(user_item.content)
        history = await self._history(thread, context)
        inputs = self._build_inputs_payload(thread, message_text, history)

        try:
            reply, _state, run = await self._run_workflow(workflow_id, inputs)
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
