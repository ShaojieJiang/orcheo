"""ChatKit-related FastAPI routes."""

from __future__ import annotations
import logging
from typing import Any
from uuid import UUID
from chatkit.server import StreamingResult
from chatkit.types import ChatKitReq
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError
from starlette.responses import JSONResponse, StreamingResponse
from orcheo.models.workflow import WorkflowRun
from orcheo.vault.oauth import CredentialHealthError
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthorizationPolicy,
    get_authorization_policy,
)
from orcheo_backend.app.chatkit_runtime import resolve_chatkit_token_issuer
from orcheo_backend.app.chatkit_service import ChatKitRequestContext
from orcheo_backend.app.chatkit_tokens import (
    ChatKitSessionTokenIssuer,
    ChatKitTokenConfigurationError,
)
from orcheo_backend.app.dependencies import RepositoryDep
from orcheo_backend.app.errors import raise_not_found
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.schemas import (
    ChatKitSessionRequest,
    ChatKitSessionResponse,
    ChatKitWorkflowTriggerRequest,
)


router = APIRouter()

logger = logging.getLogger(__name__)


@router.post("/chatkit", include_in_schema=False)
async def chatkit_gateway(request: Request) -> Response:
    """Proxy ChatKit SDK requests to the Orcheo-backed server."""
    payload = await request.body()
    from orcheo_backend.app import TypeAdapter, get_chatkit_server

    try:
        adapter: TypeAdapter[ChatKitReq] = TypeAdapter(ChatKitReq)
        parsed_request = adapter.validate_json(payload)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Invalid ChatKit payload.",
                "errors": exc.errors(),
            },
        ) from exc

    context: ChatKitRequestContext = {"chatkit_request": parsed_request}
    server = get_chatkit_server()
    result = await server.process(payload, context)

    if isinstance(result, StreamingResult):
        return StreamingResponse(result, media_type="text/event-stream")
    if hasattr(result, "json"):
        json_payload = result.json
        status_code = getattr(result, "status_code", status.HTTP_200_OK)
        headers = getattr(result, "headers", None)
        media_type = getattr(result, "media_type", "application/json")

        payload_value: Any
        if callable(json_payload):
            payload_value = json_payload()
        else:
            payload_value = json_payload

        header_mapping = dict(headers) if headers else None

        if isinstance(payload_value, str | bytes | bytearray):
            return Response(
                content=payload_value,
                status_code=status_code,
                media_type=media_type,
                headers=header_mapping,
            )

        return JSONResponse(
            payload_value,
            status_code=status_code,
            headers=header_mapping,
            media_type=media_type,
        )
    return JSONResponse(result)


def _resolve_chatkit_workspace_id(
    policy: AuthorizationPolicy, request: ChatKitSessionRequest
) -> str | None:
    metadata = request.metadata or {}
    for key in ("workspace_id", "workspaceId", "workspace"):
        value = metadata.get(key)
        if value:
            return str(value)
    if policy.context.workspace_ids:
        if len(policy.context.workspace_ids) == 1:
            return next(iter(policy.context.workspace_ids))
    return None


@router.post(
    "/chatkit/session",
    response_model=ChatKitSessionResponse,
    status_code=status.HTTP_200_OK,
)
async def create_chatkit_session_endpoint(
    request: ChatKitSessionRequest,
    policy: AuthorizationPolicy = Depends(get_authorization_policy),  # noqa: B008
    issuer: ChatKitSessionTokenIssuer = Depends(resolve_chatkit_token_issuer),  # noqa: B008
) -> ChatKitSessionResponse:
    """Issue a signed ChatKit session token scoped to the caller."""
    try:
        policy.require_authenticated()
        policy.require_scopes("chatkit:session")
    except AuthenticationError as exc:
        raise exc.as_http_exception() from exc

    workspace_id = _resolve_chatkit_workspace_id(policy, request)
    if workspace_id:
        try:
            policy.require_workspace(workspace_id)
        except AuthenticationError as exc:
            raise exc.as_http_exception() from exc

    context = policy.context
    extra: dict[str, Any] = {}
    if request.workflow_label:
        extra["workflow_label"] = request.workflow_label
    if request.current_client_secret:
        extra["previous_secret"] = request.current_client_secret
    extra_payload: dict[str, Any] | None = extra or None

    try:
        token, expires_at = issuer.mint_session(
            subject=context.subject,
            identity_type=context.identity_type,
            token_id=context.token_id,
            workspace_ids=context.workspace_ids,
            primary_workspace_id=workspace_id,
            workflow_id=request.workflow_id,
            scopes=context.scopes,
            metadata=request.metadata,
            user=request.user,
            assistant=request.assistant,
            extra=extra_payload,
        )
    except ChatKitTokenConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": str(exc),
                "hint": (
                    "Set CHATKIT_TOKEN_SIGNING_KEY (or CHATKIT_CLIENT_SECRET) to "
                    "enable ChatKit session issuance."
                ),
            },
        ) from exc
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": str(exc),
                "hint": (
                    "Set CHATKIT_TOKEN_SIGNING_KEY (or CHATKIT_CLIENT_SECRET) to "
                    "enable ChatKit session issuance."
                ),
            },
        ) from exc

    logger.info(
        "Issued ChatKit session token for subject %s workspace=%s workflow=%s",
        context.subject,
        workspace_id or "<unspecified>",
        request.workflow_id or "<none>",
    )
    return ChatKitSessionResponse(client_secret=token, expires_at=expires_at)


@router.post(
    "/chatkit/workflows/{workflow_id}/trigger",
    response_model=WorkflowRun,
    status_code=status.HTTP_201_CREATED,
)
async def trigger_chatkit_workflow(
    workflow_id: UUID,
    request: ChatKitWorkflowTriggerRequest,
    repository: RepositoryDep,
) -> WorkflowRun:
    """Create a workflow run initiated from the ChatKit interface."""
    try:
        latest_version = await repository.get_latest_version(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        raise_not_found("Workflow version not found", exc)

    payload = {
        "source": "chatkit",
        "message": request.message,
        "client_thread_id": request.client_thread_id,
        "metadata": request.metadata,
    }

    try:
        run = await repository.create_run(
            workflow_id,
            workflow_version_id=latest_version.id,
            triggered_by=request.actor,
            input_payload=payload,
        )
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        raise_not_found("Workflow version not found", exc)
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc

    logger.info(
        "Dispatched ChatKit workflow run",
        extra={"workflow_id": str(workflow_id), "run_id": str(run.id)},
    )
    return run


__all__ = ["router"]
