"""Websocket routes for workflow execution streaming."""

from __future__ import annotations
import asyncio
import uuid
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from orcheo_backend.app.authentication import AuthenticationError


router = APIRouter()

_CANNOT_SEND_AFTER_CLOSE = 'Cannot call "send" once a close message has been sent.'


@router.websocket("/ws/workflow/{workflow_id}")
async def workflow_websocket(websocket: WebSocket, workflow_id: str) -> None:
    """Handle workflow websocket connections by delegating to the executor."""
    from orcheo_backend.app import (
        authenticate_websocket,
        execute_workflow,
        execute_workflow_evaluation,
        execute_workflow_training,
    )

    try:
        context = await authenticate_websocket(websocket)
    except AuthenticationError:
        return

    subprotocol = getattr(websocket.state, "subprotocol", None)
    if subprotocol:
        await websocket.accept(subprotocol=subprotocol)
    else:
        await websocket.accept()
    websocket.state.auth = context

    try:
        while True:
            data = await websocket.receive_json()

            message_type = data.get("type")
            if message_type == "run_workflow":
                execution_id = data.get("execution_id", str(uuid.uuid4()))
                task = asyncio.create_task(
                    execute_workflow(
                        workflow_id,
                        data["graph_config"],
                        data["inputs"],
                        execution_id,
                        websocket,
                        runnable_config=data.get("runnable_config"),
                        stored_runnable_config=data.get("stored_runnable_config"),
                    )
                )

                await task
                break
            if message_type == "evaluate_workflow":
                execution_id = data.get("execution_id", str(uuid.uuid4()))
                task = asyncio.create_task(
                    execute_workflow_evaluation(
                        workflow_id,
                        data["graph_config"],
                        data.get("inputs", {}),
                        execution_id,
                        websocket,
                        evaluation=data.get("evaluation"),
                        runnable_config=data.get("runnable_config"),
                        stored_runnable_config=data.get("stored_runnable_config"),
                    )
                )
                await task
                break
            if message_type == "train_workflow":
                execution_id = data.get("execution_id", str(uuid.uuid4()))
                task = asyncio.create_task(
                    execute_workflow_training(
                        workflow_id,
                        data["graph_config"],
                        data.get("inputs", {}),
                        execution_id,
                        websocket,
                        training=data.get("training"),
                        runnable_config=data.get("runnable_config"),
                        stored_runnable_config=data.get("stored_runnable_config"),
                    )
                )
                await task
                break

            await _safe_send_error_payload(  # pragma: no cover
                websocket, {"status": "error", "error": "Invalid message type"}
            )

    except WebSocketDisconnect:
        return
    except Exception as exc:  # pragma: no cover
        await _safe_send_error_payload(
            websocket, {"status": "error", "error": str(exc)}
        )
    finally:
        await _safe_close_websocket(websocket)


async def _safe_send_error_payload(
    websocket: WebSocket,
    payload: dict[str, Any],
) -> None:
    """Send a JSON error payload if the websocket is still open."""
    try:
        await websocket.send_json(payload)
    except WebSocketDisconnect:
        return
    except RuntimeError as exc:
        if str(exc) == _CANNOT_SEND_AFTER_CLOSE:
            return
        raise


async def _safe_close_websocket(websocket: WebSocket) -> None:
    """Close the websocket without raising if the client already closed."""
    try:
        await websocket.close()
    except WebSocketDisconnect:
        return
    except RuntimeError as exc:
        if str(exc) == _CANNOT_SEND_AFTER_CLOSE:
            return
        raise


__all__ = ["router"]
