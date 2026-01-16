"""ChatKit asset proxy routes."""

from __future__ import annotations
from fastapi import APIRouter, Request, Response
from orcheo_backend.app.chatkit_asset_proxy import proxy_chatkit_asset


router = APIRouter()


@router.get("/assets/ck1/{asset_path:path}", include_in_schema=False)
@router.head("/assets/ck1/{asset_path:path}", include_in_schema=False)
async def proxy_ck1_asset(request: Request, asset_path: str) -> Response:
    return await proxy_chatkit_asset(
        request,
        prefix="assets/ck1",
        asset_path=asset_path,
    )


__all__ = ["router"]
