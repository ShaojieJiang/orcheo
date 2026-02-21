"""System metadata routes."""

from __future__ import annotations
from fastapi import APIRouter
from orcheo_backend.app.schemas.system import SystemInfoResponse
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


__all__ = ["public_router", "router"]
