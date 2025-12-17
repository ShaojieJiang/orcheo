"""Workflow execution helpers and websocket streaming utilities."""

from __future__ import annotations
import asyncio
import logging
import uuid
from collections.abc import Callable, Mapping
from typing import Any, cast
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect
from langchain_core.runnables import RunnableConfig
from opentelemetry.trace import Span, Tracer
from orcheo.config import get_settings
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
from orcheo.graph.state import State
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo.runtime.runnable_config import RunnableConfigModel, parse_runnable_config
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
from orcheo_backend.app.history import (
    RunHistoryError,
    RunHistoryRecord,
    RunHistoryStep,
    RunHistoryStore,
)
from orcheo_backend.app.trace_utils import build_trace_update


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


_CANNOT_SEND_AFTER_CLOSE = 'Cannot call "send" once a close message has been sent.'


async def _safe_send_json(websocket: WebSocket, payload: Any) -> bool:
    """Send JSON only while the websocket is open."""
    try:
        await websocket.send_json(payload)
    except WebSocketDisconnect:
        logger.debug("Websocket disconnected before payload could be sent.")
        return False
    except RuntimeError as exc:
        if str(exc) == _CANNOT_SEND_AFTER_CLOSE:
            logger.debug("Websocket already closed; skipping payload send.")
            return False
        raise
    return True


async def _emit_trace_update(
    history_store: RunHistoryStore,
    websocket: WebSocket,
    execution_id: str,
    *,
    step: RunHistoryStep | None = None,
    include_root: bool = False,
    complete: bool = False,
) -> None:
    """Fetch the latest history snapshot and stream a trace update."""
    try:
        record = await history_store.get_history(execution_id)
    except RunHistoryError:
        return
    if not isinstance(record, RunHistoryRecord):
        return

    update = build_trace_update(
        record, step=step, include_root=include_root, complete=complete
    )
    if update is not None:
        await _safe_send_json(websocket, update.model_dump(mode="json"))


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
        history_step = await history_store.append_step(execution_id, step)
        try:
            await _safe_send_json(websocket, step)
        except Exception as exc:  # pragma: no cover
            logger.error("Error processing messages: %s", exc)
            raise

        await _emit_trace_update(
            history_store,
            websocket,
            execution_id,
            step=history_step,
        )

    final_state = await compiled_graph.aget_state(cast(RunnableConfig, config))
    _log_final_state_debug(final_state.values)


async def _run_workflow_stream(
    compiled_graph: Any,
    state: Any,
    config: RunnableConfig,
    history_store: RunHistoryStore,
    execution_id: str,
    websocket: WebSocket,
    tracer: Tracer,
    span: Span,
) -> None:
    """Stream updates and handle cancellation or failure outcomes."""
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
        record_workflow_cancellation(span, reason=reason)
        cancellation_payload = {"status": "cancelled", "reason": reason}
        await history_store.append_step(execution_id, cancellation_payload)
        await history_store.mark_cancelled(execution_id, reason=reason)
        await _emit_trace_update(
            history_store,
            websocket,
            execution_id,
            include_root=True,
            complete=True,
        )
        raise
    except RunHistoryError as exc:
        _report_history_error(
            execution_id,
            span,
            exc,
            context="persist workflow history",
        )
        raise
    except Exception as exc:
        record_workflow_failure(span, exc)
        error_message = str(exc)
        error_payload = {"status": "error", "error": error_message}
        await _persist_failure_history(
            history_store,
            execution_id,
            error_payload,
            error_message,
            span,
        )
        await _emit_trace_update(
            history_store,
            websocket,
            execution_id,
            include_root=True,
            complete=True,
        )
        raise


def _report_history_error(
    execution_id: str,
    span: Span,
    exc: Exception,
    *,
    context: str,
) -> None:
    """Record tracing metadata and log a run history persistence failure."""
    record_workflow_failure(span, exc)
    logger.exception("Failed to %s for execution %s", context, execution_id)


async def _persist_failure_history(
    history_store: RunHistoryStore,
    execution_id: str,
    payload: Mapping[str, Any],
    error_message: str,
    span: Span,
) -> None:
    """Persist failure metadata while tolerating run history errors."""
    try:
        await history_store.append_step(execution_id, payload)
        await history_store.mark_failed(execution_id, error_message)
    except RunHistoryError as history_exc:
        _report_history_error(
            execution_id,
            span,
            history_exc,
            context="record failure state",
        )


def _build_initial_state(
    graph_config: Mapping[str, Any],
    inputs: dict[str, Any],
    runtime_config: Mapping[str, Any] | None,
) -> Any:
    """Return the starting runtime state for a workflow execution."""
    if graph_config.get("format") == LANGGRAPH_SCRIPT_FORMAT:
        if runtime_config is None:
            return inputs
        if isinstance(inputs, dict):
            state = dict(inputs)
            state["config"] = runtime_config
            return state
        return inputs
    return {
        "messages": [],
        "results": {},
        "inputs": inputs,
        "config": runtime_config or {},
    }


def _prepare_runnable_config(
    execution_id: str,
    candidate: Mapping[str, Any] | RunnableConfigModel | None,
) -> tuple[RunnableConfigModel, RunnableConfig, dict[str, Any], dict[str, Any]]:
    parsed_config = parse_runnable_config(candidate)
    runtime_config = parsed_config.to_runnable_config(execution_id)
    state_config = parsed_config.to_state_config(execution_id)
    stored_config = parsed_config.to_json_config(execution_id)
    return parsed_config, runtime_config, state_config, stored_config


async def execute_workflow(
    workflow_id: str,
    graph_config: dict[str, Any],
    inputs: dict[str, Any],
    execution_id: str,
    websocket: WebSocket,
    runnable_config: Mapping[str, Any] | RunnableConfigModel | None = None,
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
    parsed_config, runtime_config, state_config, stored_config = (
        _prepare_runnable_config(execution_id, runnable_config)
    )

    with workflow_span(
        tracer,
        workflow_id=workflow_id,
        execution_id=execution_id,
        inputs=inputs,
        runnable_config=parsed_config,
    ) as span_context:
        await history_store.start_run(
            workflow_id=workflow_id,
            execution_id=execution_id,
            inputs=inputs,
            trace_id=span_context.trace_id,
            trace_started_at=span_context.started_at,
            runnable_config=stored_config,
            tags=parsed_config.tags,
            callbacks=parsed_config.callbacks,
            metadata=parsed_config.metadata,
            run_name=parsed_config.run_name,
        )
        await _emit_trace_update(
            history_store,
            websocket,
            execution_id,
            include_root=True,
        )

        with credential_resolution(resolver):
            async with create_checkpointer(settings) as checkpointer:
                graph = build_graph(graph_config)
                compiled_graph = graph.compile(checkpointer=checkpointer)

                state = _build_initial_state(graph_config, inputs, state_config)
                _log_sensitive_debug("Initial state: %s", state)

                await _run_workflow_stream(
                    compiled_graph,
                    state,
                    runtime_config,
                    history_store,
                    execution_id,
                    websocket,
                    tracer,
                    span_context.span,
                )

        completion_payload = {"status": "completed"}
        record_workflow_completion(span_context.span)
        await history_store.append_step(execution_id, completion_payload)
        await history_store.mark_completed(execution_id)
        await _safe_send_json(websocket, completion_payload)  # pragma: no cover

        await _emit_trace_update(
            history_store,
            websocket,
            execution_id,
            include_root=True,
            complete=True,
        )


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
        execution_id = str(uuid.uuid4())
        _, runtime_config, state_config, _ = _prepare_runnable_config(
            execution_id, None
        )
        state: State = {
            "messages": [],
            "results": {},
            "inputs": inputs,
            "structured_response": None,
            "config": state_config,
        }
        return await node_instance(state, runtime_config)


__all__ = [
    "configure_sensitive_logging",
    "execute_node",
    "execute_workflow",
]
