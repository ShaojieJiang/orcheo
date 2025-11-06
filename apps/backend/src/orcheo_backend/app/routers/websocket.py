"""Websocket routes for workflow execution streaming."""

from __future__ import annotations
import asyncio
import uuid
from fastapi import APIRouter, WebSocket
from orcheo_backend.app.authentication import AuthenticationError


router = APIRouter()


@router.websocket("/ws/workflow/{workflow_id}")
async def workflow_websocket(websocket: WebSocket, workflow_id: str) -> None:
    """Handle workflow websocket connections by delegating to the executor."""
    from orcheo_backend.app import authenticate_websocket, execute_workflow

    try:
        context = await authenticate_websocket(websocket)
    except AuthenticationError:
        return

    await websocket.accept()
    websocket.state.auth = context

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "run_workflow":
                execution_id = data.get("execution_id", str(uuid.uuid4()))
                task = asyncio.create_task(
                    execute_workflow(
                        workflow_id,
                        data["graph_config"],
                        data["inputs"],
                        execution_id,
                        websocket,
                    )
                )

                await task
                break

            await websocket.send_json(  # pragma: no cover
                {"status": "error", "error": "Invalid message type"}
            )

    except Exception as exc:  # pragma: no cover
        await websocket.send_json({"status": "error", "error": str(exc)})
    finally:
        await websocket.close()


__all__ = ["router"]
