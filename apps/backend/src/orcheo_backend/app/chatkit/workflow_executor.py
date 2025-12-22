"""Workflow execution helpers for the ChatKit server."""

from __future__ import annotations
import logging
from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID, uuid4
from chatkit.errors import CustomStreamError
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo.models import CredentialAccessContext
from orcheo.persistence import create_checkpointer
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.runtime.runnable_config import merge_runnable_configs
from orcheo.vault import BaseCredentialVault
from orcheo_backend.app.chatkit.message_utils import (
    build_initial_state,
    extract_reply_from_state,
)
from orcheo_backend.app.repository import WorkflowRepository, WorkflowRun


logger = logging.getLogger(__name__)


class WorkflowExecutor:
    """Encapsulates the workflow execution path for ChatKit requests."""

    def __init__(
        self,
        repository: WorkflowRepository,
        vault_provider: Callable[[], BaseCredentialVault],
    ) -> None:
        """Store collaborators used during workflow execution."""
        self._repository = repository
        self._vault_provider = vault_provider

    async def run(
        self,
        workflow_id: UUID,
        inputs: Mapping[str, Any],
        *,
        actor: str = "chatkit",
    ) -> tuple[str, Mapping[str, Any], WorkflowRun | None]:
        """Execute the workflow and return the reply, state view, and run."""
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
            initial_state = build_initial_state(graph_config, inputs)
            payload: Any = initial_state
            execution_id = str(uuid4())
            merged_config = merge_runnable_configs(version.runnable_config, None)
            config: RunnableConfig = merged_config.to_runnable_config(execution_id)
            with credential_resolution(credential_resolver):
                final_state = await compiled.ainvoke(payload, config=config)

        raw_messages = self._extract_messages(final_state)

        if isinstance(final_state, BaseModel):
            state_view: Mapping[str, Any] = final_state.model_dump()
        elif isinstance(final_state, Mapping):
            state_view = dict(final_state)
        else:  # pragma: no cover - defensive
            state_view = dict(final_state or {})

        if raw_messages:
            if not isinstance(state_view, dict):  # pragma: no branch
                state_view = dict(state_view)
            state_view["_messages"] = raw_messages

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

    @staticmethod
    def _extract_messages(final_state: Any) -> list[BaseMessage]:
        """Return LangChain messages from the workflow state when available."""
        candidates = []
        if isinstance(final_state, Mapping):
            maybe_messages = final_state.get("messages")
            if isinstance(maybe_messages, list):
                candidates = maybe_messages
        if not candidates and hasattr(final_state, "messages"):
            maybe_messages = final_state.messages  # type: ignore[attr-defined]
            if isinstance(maybe_messages, list):  # pragma: no branch
                candidates = maybe_messages

        return [
            message
            for message in candidates
            if isinstance(message, BaseMessage)  # type: ignore[arg-type]
        ]


__all__ = ["WorkflowExecutor"]
