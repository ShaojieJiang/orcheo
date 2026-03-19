"""System metadata routes."""

from __future__ import annotations
from fastapi import APIRouter
from orcheo_backend.app.plugin_inventory import list_runtime_plugins
from orcheo_backend.app.schemas.system import (
    SystemInfoResponse,
    SystemPluginsResponse,
)
from orcheo_backend.app.versioning import get_system_info_payload


public_router = APIRouter()
router = APIRouter()


@public_router.get("/system/health")
def get_system_health() -> dict[str, str]:
    """Return a lightweight unauthenticated health status."""
    return {"status": "ok"}


@router.get("/system/info", response_model=SystemInfoResponse)
def get_system_info() -> SystemInfoResponse:
    """Return current and latest version metadata for Orcheo components."""
    return SystemInfoResponse.model_validate(get_system_info_payload())


@router.get("/system/plugins", response_model=SystemPluginsResponse)
def get_system_plugins() -> SystemPluginsResponse:
    """Return plugin availability for the current backend process."""
    return SystemPluginsResponse.model_validate({"plugins": list_runtime_plugins()})


__all__ = ["public_router", "router"]
