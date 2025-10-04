"""Backend entrypoint package for the Orcheo FastAPI service."""

from fastapi import FastAPI
from .app import app, create_app, execute_workflow, workflow_websocket


__all__ = [
    "app",
    "create_app",
    "execute_workflow",
    "workflow_websocket",
    "get_app",
]


def get_app() -> FastAPI:
    """Return the FastAPI application instance for deployment entrypoints."""
    return app
