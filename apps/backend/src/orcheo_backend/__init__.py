"""Backend entrypoint package for the Orcheo FastAPI service."""

from fastapi import FastAPI
from orcheo_backend.app import (
    app,
    create_app,
    execute_workflow,
    get_repository,
    workflow_websocket,
)


__all__ = [
    "app",
    "create_app",
    "execute_workflow",
    "get_repository",
    "workflow_websocket",
    "get_app",
]


def get_app() -> FastAPI:  # pragma: no cover
    """Return the FastAPI application instance for deployment entrypoints."""
    return app
