"""Workflow execution helpers for the ChatKit server."""

from __future__ import annotations
import logging
from collections.abc import Awaitable, Callable, Mapping
from contextlib import nullcontext
from typing import Any
from uuid import UUID, uuid4
from chatkit.errors import CustomStreamError
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel
from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo.models import CredentialAccessContext
from orcheo.nodes.agent_tools.context import tool_progress_context
from orcheo.persistence import create_checkpointer
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.runtime.runnable_config import merge_runnable_configs
from orcheo.vault import BaseCredentialVault
from orcheo_backend.app.chatkit.message_utils import (
    build_initial_state,
    extract_reply_from_state,
)
from orcheo_backend.app.dependencies import get_history_store
from orcheo_backend.app.history import RunHistoryError, RunHistoryStore
from orcheo_backend.app.repository import WorkflowRepository, WorkflowRun


logger = logging.getLogger(__name__)


async def _start_chatkit_history(
    *,
    history_store: RunHistoryStore,
    workflow_id: UUID,
    execution_id: str,
    inputs: Mapping[str, Any],
    merged_config: Any,
) -> None:
    """Persist run metadata in execution history for ChatKit executions."""
    try:
        await history_store.start_run(
            workflow_id=str(workflow_id),
            execution_id=execution_id,
            inputs=dict(inputs),
            runnable_config=merged_config.to_json_config(execution_id),
            tags=merged_config.tags,
            callbacks=merged_config.callbacks,
            metadata=merged_config.metadata,
            run_name=merged_config.run_name,
        )
    except RunHistoryError:
        logger.exception(
            "Failed to start chatkit run history for execution %s",
            execution_id,
        )


async def _append_chatkit_history_step(
    history_store: RunHistoryStore,
    execution_id: str,
    step: Mapping[str, Any],
) -> None:
    """Append a streamed node step to ChatKit execution history."""
    try:
        await history_store.append_step(execution_id, step)
    except RunHistoryError:
        logger.exception(
            "Failed to append chatkit history step for execution %s",
            execution_id,
        )


async def _mark_chatkit_history_completed(
    history_store: RunHistoryStore,
    execution_id: str,
) -> None:
    """Mark a ChatKit execution history entry as completed."""
    try:
        await history_store.append_step(execution_id, {"status": "completed"})
        await history_store.mark_completed(execution_id)
    except RunHistoryError:
        logger.exception(
            "Failed to mark chatkit history completed for execution %s",
            execution_id,
        )


async def _mark_chatkit_history_failed(
    history_store: RunHistoryStore,
    execution_id: str,
    error_message: str,
) -> None:
    """Mark a ChatKit execution history entry as failed."""
    try:
        await history_store.append_step(
            execution_id,
            {"status": "error", "error": error_message},
        )
        await history_store.mark_failed(execution_id, error_message)
    except RunHistoryError:
        logger.exception(
            "Failed to mark chatkit history failed for execution %s",
            execution_id,
        )


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
        progress_callback: Callable[[Mapping[str, Any]], Awaitable[None]] | None = None,
    ) -> tuple[str, Mapping[str, Any], WorkflowRun | None]:
        """Execute the workflow and return the reply, state view, and run."""
        version = await self._repository.get_latest_version(workflow_id)
        history_store = get_history_store()
        run = await self._create_run_record(workflow_id, version.id, actor, inputs)
        execution_id = self._resolve_execution_id(run)
        merged_config = merge_runnable_configs(version.runnable_config, None)
        config: RunnableConfig = merged_config.to_runnable_config(execution_id)

        await _start_chatkit_history(
            history_store=history_store,
            workflow_id=workflow_id,
            execution_id=execution_id,
            inputs=inputs,
            merged_config=merged_config,
        )

        try:
            step_callback = None
            if progress_callback is not None:
                step_callback = self._build_step_callback(
                    history_store=history_store,
                    execution_id=execution_id,
                    progress_callback=progress_callback,
                )
            final_state = await self._execute_graph(
                workflow_id=workflow_id,
                graph_config=version.graph,
                inputs=inputs,
                config=config,
                step_callback=step_callback,
            )
            reply, state_view = self._build_reply_state(final_state)
        except Exception as exc:
            await self._record_run_failure(
                run=run,
                actor=actor,
                history_store=history_store,
                execution_id=execution_id,
                error_message=str(exc),
            )
            raise

        await _mark_chatkit_history_completed(history_store, execution_id)
        await self._mark_run_succeeded(run, actor, reply)
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

    @staticmethod
    def _resolve_execution_id(run: WorkflowRun | None) -> str:
        """Return a stable execution identifier for trace history records."""
        if run is not None:
            return str(run.id)
        return str(uuid4())

    async def _create_run_record(
        self,
        workflow_id: UUID,
        workflow_version_id: UUID,
        actor: str,
        inputs: Mapping[str, Any],
    ) -> WorkflowRun | None:
        """Create and start a repository run record when possible."""
        try:
            run = await self._repository.create_run(
                workflow_id,
                workflow_version_id=workflow_version_id,
                triggered_by=actor,
                input_payload=dict(inputs),
            )
            await self._repository.mark_run_started(run.id, actor=actor)
            return run
        except Exception:  # pragma: no cover - repository failure
            logger.exception("Failed to record workflow run metadata")
            return None

    def _build_step_callback(
        self,
        *,
        history_store: RunHistoryStore,
        execution_id: str,
        progress_callback: Callable[[Mapping[str, Any]], Awaitable[None]] | None,
    ) -> Callable[[Mapping[str, Any]], Awaitable[None]]:
        """Create a callback that persists history then forwards UI progress."""

        async def _handle_step(step: Mapping[str, Any]) -> None:
            await _append_chatkit_history_step(history_store, execution_id, step)
            if progress_callback is not None:
                await progress_callback(step)

        return _handle_step

    async def _execute_graph(
        self,
        *,
        workflow_id: UUID,
        graph_config: Mapping[str, Any],
        inputs: Mapping[str, Any],
        config: RunnableConfig,
        step_callback: Callable[[Mapping[str, Any]], Awaitable[None]] | None,
    ) -> Any:
        """Execute the compiled graph and return the final state payload."""
        settings = get_settings()
        vault = self._vault_provider()
        credential_context = CredentialAccessContext(workflow_id=workflow_id)
        credential_resolver = CredentialResolver(vault, context=credential_context)

        async with create_checkpointer(settings) as checkpointer:
            graph = build_graph(graph_config)
            compiled = graph.compile(checkpointer=checkpointer)
            payload: Any = build_initial_state(graph_config, inputs)

            with credential_resolution(credential_resolver):
                if (
                    step_callback is not None
                    and hasattr(compiled, "astream")
                    and hasattr(compiled, "aget_state")
                ):
                    progress_context = (
                        tool_progress_context(step_callback)
                        if step_callback is not None
                        else nullcontext()
                    )
                    with progress_context:
                        async for step in compiled.astream(
                            payload,
                            config=config,  # type: ignore[arg-type]
                            stream_mode="updates",
                        ):
                            if step_callback is not None:  # pragma: no branch
                                await step_callback(step)
                        snapshot = await compiled.aget_state(  # type: ignore[arg-type]
                            config
                        )
                        return getattr(snapshot, "values", snapshot)

                return await compiled.ainvoke(payload, config=config)

    def _build_reply_state(self, final_state: Any) -> tuple[str, Mapping[str, Any]]:
        """Extract reply text and normalized state view from final graph state."""
        raw_messages = self._extract_messages(final_state)

        if isinstance(final_state, BaseModel):
            state_view: Mapping[str, Any] = final_state.model_dump()
        elif isinstance(final_state, Mapping):
            state_view = dict(final_state)
        else:  # pragma: no cover - defensive
            state_view = dict(final_state or {})

        state_view = dict(state_view)
        if raw_messages:
            state_view["_messages"] = raw_messages

        reply = extract_reply_from_state(state_view)
        if reply is None:
            raise CustomStreamError(
                "Workflow completed without producing a reply.",
                allow_retry=False,
            )
        return reply, state_view

    async def _mark_run_succeeded(
        self,
        run: WorkflowRun | None,
        actor: str,
        reply: str,
    ) -> None:
        """Mark the repository run as succeeded, logging failures only."""
        if run is None:
            return
        try:
            await self._repository.mark_run_succeeded(
                run.id,
                actor=actor,
                output={"reply": reply},
            )
        except Exception:  # pragma: no cover - repository failure
            logger.exception("Failed to mark workflow run succeeded")

    async def _record_run_failure(
        self,
        *,
        run: WorkflowRun | None,
        actor: str,
        history_store: RunHistoryStore,
        execution_id: str,
        error_message: str,
    ) -> None:
        """Record repository and history failure states for ChatKit execution."""
        await _mark_chatkit_history_failed(
            history_store,
            execution_id,
            error_message,
        )
        if run is None:
            return
        try:
            await self._repository.mark_run_failed(
                run.id,
                actor=actor,
                error=error_message,
            )
        except Exception:  # pragma: no cover - repository failure
            logger.exception("Failed to mark workflow run failed")


__all__ = ["WorkflowExecutor"]
