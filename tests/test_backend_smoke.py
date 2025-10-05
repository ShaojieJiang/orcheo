"""Smoke tests for the FastAPI deployment wrapper."""

from importlib import import_module
from fastapi import FastAPI


def test_backend_app_imports() -> None:
    """Ensure the deployment wrapper module imports without errors."""
    module = import_module("orcheo_backend.app")
    assert hasattr(module, "app")
    assert hasattr(module, "create_app")


def test_create_app_returns_fastapi_instance() -> None:
    """Assert the app factory exposes the workflow websocket route."""
    module = import_module("orcheo_backend.app")
    app = module.create_app()
    assert isinstance(app, FastAPI)
    websocket_paths = {
        route.path for route in app.router.routes if getattr(route, "path", None)
    }
    assert "/ws/workflow/{workflow_id}" in websocket_paths


def test_get_app_matches_module_level_app() -> None:
    """Verify the exported get_app helper returns the module-level FastAPI instance."""
    module = import_module("orcheo_backend.app")
    from orcheo_backend import get_app

    assert isinstance(module.app, FastAPI)
    assert get_app() is module.app
