"""Workflow execution helpers and websocket streaming utilities."""

from __future__ import annotations
import asyncio
import logging
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID
from fastapi import WebSocket
from langchain_core.runnables import RunnableConfig
from opentelemetry.trace import Span, Status, StatusCode
from orcheo.config import get_settings
from orcheo.graph.ingestion import LANGGRAPH_SCRIPT_FORMAT
from orcheo.graph.state import State
from orcheo.runtime.credentials import CredentialResolver, credential_resolution
from orcheo_backend.app.dependencies import (
    credential_context_from_workflow,
    get_history_store,
    get_vault,
)
from orcheo_backend.app.history import RunHistoryStore
from orcheo_backend.app.tracing import (
    add_step_event,
    add_workflow_inputs_event,
    build_step_span_attributes,
    format_trace_identifiers,
    get_workflow_tracer,
    workflow_span_attributes,
)


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
    *,
    workflow_span: Span,
) -> int:
    """Stream workflow updates to the client while recording history."""
    tracer = get_workflow_tracer()
    last_step_index = -1
    try:
        async for step in compiled_graph.astream(
            state,
            config=config,  # type: ignore[arg-type]
            stream_mode="updates",
        ):  # pragma: no cover
            _log_step_debug(step)
            step_record = await history_store.append_step(execution_id, step)
            last_step_index = step_record.index

            for node_name, node_output in step.items():
                attributes = build_step_span_attributes(
                    step_index=step_record.index,
                    node_name=node_name,
                    payload=node_output,
                )
                with tracer.start_as_current_span(
                    name=f"workflow.step.{node_name}",
                    attributes=attributes,
                ) as node_span:
                    add_step_event(
                        node_span,
                        step_index=step_record.index,
                        node_name=node_name,
                        payload=node_output,
                    )
            add_step_event(
                workflow_span,
                step_index=step_record.index,
                node_name="workflow.step",
                payload=step,
            )
            try:
                await websocket.send_json(step)
            except Exception as exc:  # pragma: no cover
                logger.error("Error processing messages: %s", exc)
                workflow_span.record_exception(exc)
                workflow_span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise

        final_state = await compiled_graph.aget_state(cast(RunnableConfig, config))
        _log_final_state_debug(final_state.values)
        add_step_event(
            workflow_span,
            step_index=last_step_index if last_step_index >= 0 else 0,
            node_name="workflow.final_state",
            payload={"state": final_state.values},
        )
    except asyncio.CancelledError as exc:
        reason = str(exc) or "Workflow execution cancelled"
        cancellation_payload = {"status": "cancelled", "reason": reason}
        cancelled_step = await history_store.append_step(
            execution_id, cancellation_payload
        )
        add_step_event(
            workflow_span,
            step_index=cancelled_step.index,
            node_name="workflow.cancelled",
            payload=cancellation_payload,
        )
        await history_store.mark_cancelled(execution_id, reason=reason)
        workflow_span.set_attribute("workflow.status", "cancelled")
        workflow_span.record_exception(exc)
        workflow_span.set_status(Status(StatusCode.ERROR, reason))
        raise
    except Exception as exc:
        error_payload = {"status": "error", "error": str(exc)}
        error_step = await history_store.append_step(execution_id, error_payload)
        add_step_event(
            workflow_span,
            step_index=error_step.index,
            node_name="workflow.error",
            payload=error_payload,
        )
        await history_store.mark_failed(execution_id, str(exc))
        workflow_span.set_attribute("workflow.status", "error")
        workflow_span.record_exception(exc)
        workflow_span.set_status(Status(StatusCode.ERROR, str(exc)))
        raise
    return last_step_index


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
    tracer = get_workflow_tracer()
    span_attributes = workflow_span_attributes(
        workflow_id=workflow_id, execution_id=execution_id
    )

    with tracer.start_as_current_span(
        "workflow.execute", attributes=span_attributes
    ) as workflow_span:
        trace_started_at = datetime.now(tz=UTC)
        trace_id, root_span_id = format_trace_identifiers(workflow_span)

        await history_store.start_run(
            workflow_id=workflow_id,
            execution_id=execution_id,
            inputs=inputs,
            trace_id=trace_id,
            root_span_id=root_span_id,
            trace_started_at=trace_started_at,
        )

        add_workflow_inputs_event(workflow_span, inputs)

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
                await _stream_workflow_updates(
                    compiled_graph,
                    state,
                    config,
                    history_store,
                    execution_id,
                    websocket,
                    workflow_span=workflow_span,
                )

        completion_payload = {"status": "completed"}
        completion_step = await history_store.append_step(
            execution_id, completion_payload
        )
        add_step_event(
            workflow_span,
            step_index=completion_step.index,
            node_name="workflow.completed",
            payload=completion_payload,
        )
        await history_store.mark_completed(execution_id)
        workflow_span.set_attribute("workflow.status", "completed")
        workflow_span.set_status(Status(StatusCode.OK))
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
