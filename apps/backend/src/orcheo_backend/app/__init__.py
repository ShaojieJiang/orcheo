"""FastAPI application entrypoint for the Orcheo backend service."""

import asyncio
import logging
import uuid
from typing import Any
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from orcheo.config import get_settings
from orcheo.graph.builder import build_graph
from orcheo.persistence import create_checkpointer


# Configure logging for the backend module once on import.
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

router = APIRouter()


async def execute_workflow(
    workflow_id: str,
    graph_config: dict[str, Any],
    inputs: dict[str, Any],
    execution_id: str,
    websocket: WebSocket,
) -> None:
    """Execute a workflow and stream results over the provided websocket."""
    logger.info("Starting workflow %s with execution_id: %s", workflow_id, execution_id)
    logger.info("Initial inputs: %s", inputs)

    settings = get_settings()
    async with create_checkpointer(settings) as checkpointer:
        graph = build_graph(graph_config)
        compiled_graph = graph.compile(checkpointer=checkpointer)

        # Initialize state
        state = {"messages": [], **inputs}
        logger.info("Initial state: %s", state)

        # Run graph with streaming
        config = {"configurable": {"thread_id": execution_id}}
        async for step in compiled_graph.astream(
            state,
            config=config,  # type: ignore[arg-type]
            stream_mode="updates",
        ):  # pragma: no cover
            try:
                await websocket.send_json(step)
            except Exception as exc:  # pragma: no cover
                logger.error("Error processing messages: %s", exc)
                raise

    await websocket.send_json({"status": "completed"})  # pragma: no cover


@router.websocket("/ws/workflow/{workflow_id}")
async def workflow_websocket(websocket: WebSocket, workflow_id: str) -> None:
    """Handle workflow websocket connections by delegating to the executor."""
    await websocket.accept()

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


def create_app() -> FastAPI:
    """Instantiate and configure the FastAPI application."""
    application = FastAPI()

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router)

    return application


app = create_app()


__all__ = ["app", "create_app", "execute_workflow", "workflow_websocket"]


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
