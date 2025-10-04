"""Backend entrypoint package for the Orcheo FastAPI service."""

from fastapi import FastAPI
from orcheo.main import app as core_app


__all__ = ["app", "create_app"]


def create_app() -> FastAPI:
    """Return the FastAPI application instance for deployment entrypoints."""
    return core_app


app: FastAPI = create_app()
