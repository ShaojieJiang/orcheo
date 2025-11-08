"""Application factory for the Orcheo FastAPI service."""

from __future__ import annotations
from contextlib import asynccontextmanager
from typing import Any
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from orcheo.vault.oauth import OAuthCredentialService
from orcheo_backend.app.authentication import authenticate_request
from orcheo_backend.app.chatkit_runtime import (
    cancel_chatkit_cleanup_task,
    ensure_chatkit_cleanup_task,
    get_chatkit_server,
    sensitive_logging_enabled,
)
from orcheo_backend.app.dependencies import (
    get_credential_service,
    get_history_store,
    get_repository,
    set_credential_service,
    set_history_store,
    set_repository,
    set_vault,
)
from orcheo_backend.app.history import RunHistoryStore
from orcheo_backend.app.logging_config import configure_logging
from orcheo_backend.app.repository import WorkflowRepository
from orcheo_backend.app.routers import (
    chatkit as chatkit_router,
)
from orcheo_backend.app.routers import (
    credential_alerts,
    credential_health,
    credential_templates,
    credentials,
    nodes,
    runs,
    triggers,
    websocket,
    workflows,
)
from orcheo_backend.app.service_token_endpoints import router as service_token_router
from orcheo_backend.app.workflow_execution import configure_sensitive_logging


load_dotenv()
configure_logging()

configure_sensitive_logging(
    enable_sensitive_debug=sensitive_logging_enabled(),
)


def _build_api_router() -> APIRouter:
    router = APIRouter(prefix="/api")

    protected_router = APIRouter(dependencies=[Depends(authenticate_request)])
    protected_router.include_router(service_token_router)
    protected_router.include_router(workflows.router)
    protected_router.include_router(credentials.router)
    protected_router.include_router(credential_templates.router)
    protected_router.include_router(credential_alerts.router)
    protected_router.include_router(credential_health.router)
    protected_router.include_router(runs.router)
    protected_router.include_router(triggers.router)
    protected_router.include_router(nodes.router)

    router.include_router(chatkit_router.router)
    router.include_router(protected_router)
    return router


api_router = _build_api_router()


def create_app(
    repository: WorkflowRepository | None = None,
    *,
    history_store: RunHistoryStore | None = None,
    credential_service: OAuthCredentialService | None = None,
) -> FastAPI:
    """Instantiate and configure the FastAPI application."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        """Manage application lifespan with startup and shutdown logic."""
        try:
            get_chatkit_server()
            await ensure_chatkit_cleanup_task()
        except Exception:
            pass
        yield
        await cancel_chatkit_cleanup_task()

    application = FastAPI(lifespan=lifespan)

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if repository is not None:
        set_repository(repository)  # pragma: no mutate - override for tests
        application.dependency_overrides[get_repository] = lambda: repository
    if history_store is not None:
        set_history_store(history_store)
        application.dependency_overrides[get_history_store] = lambda: history_store
    if credential_service is not None:
        set_credential_service(credential_service)
        set_vault(getattr(credential_service, "_vault", None))
        application.dependency_overrides[get_credential_service] = (
            lambda: credential_service
        )
    elif repository is not None:
        inferred_service = getattr(repository, "_credential_service", None)
        if inferred_service is not None:
            set_credential_service(inferred_service)
            application.dependency_overrides[get_credential_service] = (
                lambda: inferred_service
            )

    application.include_router(api_router)
    application.include_router(websocket.router)

    return application


__all__ = ["create_app"]
