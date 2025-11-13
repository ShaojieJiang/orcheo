"""Workflow execution helpers and websocket streaming utilities."""

from __future__ import annotations
import asyncio
import logging
import uuid
from collections.abc import Callable, Mapping
from typing import Any, cast
from uuid import UUID
from fastapi import WebSocket
from langchain_core.runnables import RunnableConfig
from opentelemetry.trace import Tracer
from orcheo.config import get_settings
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
from orcheo.graph.state import State
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.tracing import (
    get_tracer,
    record_workflow_cancellation,
    record_workflow_completion,
    record_workflow_failure,
    record_workflow_step,
    workflow_span,
)
from orcheo_backend.app.dependencies import (
    credential_context_from_workflow,
    get_history_store,
    get_vault,
)
from orcheo_backend.app.history import RunHistoryStore


logger = logging.getLogger(__name__)

_should_log_sensitive_debug = False


def configure_sensitive_logging(
    *,
    enable_sensitive_debug: bool,
) -> None:
    """Enable or disable sensitive debug logging."""
    global _should_log_sensitive_debug  # noqa: PLW0603
    _should_log_sensitive_debug = enable_sensitive_debug


def _log_sensitive_debug(message: str, *args: Any) -> None:
    if _should_log_sensitive_debug:
        from orcheo_backend.app import logger as app_logger

        app_logger.debug(message, *args)


def _log_step_debug(step: Mapping[str, Any]) -> None:
    if not _should_log_sensitive_debug:
        return
    from orcheo_backend.app import logger as app_logger

    for node_name, node_output in step.items():
        app_logger.debug("=" * 80)
        app_logger.debug("Node executed: %s", node_name)
        app_logger.debug("Node output: %s", node_output)
        app_logger.debug("=" * 80)


def _log_final_state_debug(state_values: Mapping[str, Any] | Any) -> None:
    if not _should_log_sensitive_debug:
        return
    from orcheo_backend.app import logger as app_logger

    app_logger.debug("=" * 80)
    app_logger.debug("Final state values: %s", state_values)
    app_logger.debug("=" * 80)


async def _stream_workflow_updates(
    compiled_graph: Any,
    state: Any,
    config: RunnableConfig,
    history_store: RunHistoryStore,
    execution_id: str,
    websocket: WebSocket,
    tracer: Tracer,
) -> None:
    """Stream workflow updates to the client while recording history."""
    async for step in compiled_graph.astream(
        state,
        config=config,  # type: ignore[arg-type]
        stream_mode="updates",
    ):  # pragma: no cover
        _log_step_debug(step)
        record_workflow_step(tracer, step)
        await history_store.append_step(execution_id, step)
        try:
            await websocket.send_json(step)
        except Exception as exc:  # pragma: no cover
            logger.error("Error processing messages: %s", exc)
            raise

    final_state = await compiled_graph.aget_state(cast(RunnableConfig, config))
    _log_final_state_debug(final_state.values)


async def execute_workflow(
    workflow_id: str,
    graph_config: dict[str, Any],
    inputs: dict[str, Any],
    execution_id: str,
    websocket: WebSocket,
) -> None:
    """Execute a workflow and stream results over the provided websocket."""
    from orcheo_backend.app import build_graph, create_checkpointer

    logger.info("Starting workflow %s with execution_id: %s", workflow_id, execution_id)
    _log_sensitive_debug("Initial inputs: %s", inputs)

    settings = get_settings()
    history_store = get_history_store()
    vault = get_vault()
    workflow_uuid: UUID | None = None
    try:
        workflow_uuid = UUID(workflow_id)
    except ValueError:
        pass
    credential_context = credential_context_from_workflow(workflow_uuid)
    resolver = CredentialResolver(vault, context=credential_context)
    tracer = get_tracer(__name__)

    with workflow_span(
        tracer,
        workflow_id=workflow_id,
        execution_id=execution_id,
        inputs=inputs,
    ) as span_context:
        await history_store.start_run(
            workflow_id=workflow_id,
            execution_id=execution_id,
            inputs=inputs,
            trace_id=span_context.trace_id,
            trace_started_at=span_context.started_at,
        )

        with credential_resolution(resolver):
            async with create_checkpointer(settings) as checkpointer:
                graph = build_graph(graph_config)
                compiled_graph = graph.compile(checkpointer=checkpointer)

                if graph_config.get("format") == LANGGRAPH_SCRIPT_FORMAT:
                    state: Any = inputs
                else:
                    state = {
                        "messages": [],
                        "results": {},
                        "inputs": inputs,
                    }
                _log_sensitive_debug("Initial state: %s", state)

                config: RunnableConfig = {"configurable": {"thread_id": execution_id}}
                try:
                    await _stream_workflow_updates(
                        compiled_graph,
                        state,
                        config,
                        history_store,
                        execution_id,
                        websocket,
                        tracer,
                    )
                except asyncio.CancelledError as exc:
                    reason = str(exc) or "Workflow execution cancelled"
                    record_workflow_cancellation(span_context.span, reason=reason)
                    cancellation_payload = {"status": "cancelled", "reason": reason}
                    await history_store.append_step(execution_id, cancellation_payload)
                    await history_store.mark_cancelled(execution_id, reason=reason)
                    raise
                except Exception as exc:
                    record_workflow_failure(span_context.span, exc)
                    error_payload = {"status": "error", "error": str(exc)}
                    await history_store.append_step(execution_id, error_payload)
                    await history_store.mark_failed(execution_id, str(exc))
                    raise

        completion_payload = {"status": "completed"}
        record_workflow_completion(span_context.span)
        await history_store.append_step(execution_id, completion_payload)
        await history_store.mark_completed(execution_id)
        await websocket.send_json(completion_payload)  # pragma: no cover


async def execute_node(
    node_class: Callable[..., Any],
    node_params: dict[str, Any],
    inputs: dict[str, Any],
    workflow_id: UUID | None = None,
) -> Any:
    """Execute a single node instance with credential resolution."""
    vault = get_vault()
    context = credential_context_from_workflow(workflow_id)
    resolver = CredentialResolver(vault, context=context)

    with credential_resolution(resolver):
        node_instance = node_class(**node_params)
        state: State = {
            "messages": [],
            "results": {},
            "inputs": inputs,
            "structured_response": None,
        }
        config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}
        return await node_instance(state, config)


__all__ = [
    "configure_sensitive_logging",
    "execute_node",
    "execute_workflow",
]
