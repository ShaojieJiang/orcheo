"""FastAPI server for Orcheo."""

import asyncio
import logging
import uuid
from typing import Any
import aiosqlite
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from orcheo.graph.builder import build_graph


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def execute_workflow(
    workflow_id: str,
    graph_config: dict[str, Any],
    inputs: dict[str, Any],
    execution_id: str,
    websocket: WebSocket,
) -> None:
    """Execute a workflow."""
    try:
        logger.info(
            f"Starting workflow {workflow_id} with execution_id: {execution_id}"
        )
        logger.info(f"Initial inputs: {inputs}")

        # Create graph from config
        async with aiosqlite.connect("checkpoints.sqlite") as conn:
            checkpointer = AsyncSqliteSaver(conn)
            graph = build_graph(graph_config)
            compiled_graph = graph.compile(checkpointer=checkpointer)

            # Initialize state
            state = {"messages": [], **inputs}
            logger.info(f"Initial state: {state}")

            # Run graph with streaming
            config = {"configurable": {"thread_id": execution_id}}
            async for step in compiled_graph.astream(
                state,
                config=config,  # type: ignore[arg-type]
                stream_mode="updates",
            ):  # pragma: no cover
                try:
                    # Send state update
                    await websocket.send_json(step)
                except Exception as e:
                    logger.error(f"Error processing messages: {e}")
                    raise

        await websocket.send_json({"status": "completed"})  # pragma: no cover

    except Exception as e:  # pragma: no cover
        logger.error(f"Workflow error: {str(e)}", exc_info=True)
        await websocket.send_json({"status": "error", "error": str(e)})


@app.websocket("/ws/workflow/{workflow_id}")
async def workflow_websocket(websocket: WebSocket, workflow_id: str) -> None:
    """Handle a workflow websocket connection."""
    await websocket.accept()

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            if data.get("type") == "run_workflow":
                # Create and store workflow task
                task = asyncio.create_task(
                    execute_workflow(
                        workflow_id,
                        data["graph_config"],
                        data["inputs"],
                        data.get("execution_id", str(uuid.uuid4())),
                        websocket,
                    )
                )

                # Wait for completion
                await task
                break
            else:  # pragma: no cover
                await websocket.send_json(
                    {"status": "error", "error": "Invalid message type"}
                )

    except Exception as e:  # pragma: no cover
        await websocket.send_json({"status": "error", "error": str(e)})
    finally:
        await websocket.close()


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
