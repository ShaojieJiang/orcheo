"""Workflow trigger routes."""

from __future__ import annotations
import json
import logging
from typing import Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from orcheo.models.workflow import WorkflowRun
from orcheo.triggers.cron import CronTriggerConfig
from orcheo.triggers.manual import ManualDispatchRequest
from orcheo.triggers.webhook import WebhookTriggerConfig, WebhookValidationError
from orcheo.vault.oauth import CredentialHealthError
from orcheo_backend.app.dependencies import RepositoryDep
from orcheo_backend.app.errors import raise_not_found, raise_webhook_error
from orcheo_backend.app.repository import (
    WorkflowNotFoundError,
    WorkflowVersionNotFoundError,
)
from orcheo_backend.app.schemas.runs import CronDispatchRequest


logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_webhook_body(
    raw_body: bytes, *, preserve_raw_body: bool
) -> tuple[Any, dict[str, Any] | None]:
    if not raw_body:
        return {}, None

    decoded_body = raw_body.decode("utf-8", errors="replace")
    parsed_body: Any | None = None
    try:
        parsed_body = json.loads(decoded_body)
    except json.JSONDecodeError:
        parsed_body = None

    if preserve_raw_body:
        payload: Any = {"raw": decoded_body}
        if parsed_body is not None:  # pragma: no branch
            payload["parsed"] = parsed_body
        return payload, parsed_body if isinstance(parsed_body, dict) else None

    payload = parsed_body if parsed_body is not None else raw_body
    return payload, parsed_body if isinstance(parsed_body, dict) else None


def _maybe_handle_slack_url_verification(
    parsed_body: dict[str, Any] | None,
) -> JSONResponse | None:
    if not parsed_body or parsed_body.get("type") != "url_verification":
        return None

    challenge = parsed_body.get("challenge")
    if not isinstance(challenge, str) or not challenge.strip():
        raise HTTPException(
            status_code=400,
            detail="Missing Slack challenge value",
        )
    return JSONResponse(content={"challenge": challenge})


@router.put(
    "/workflows/{workflow_id}/triggers/webhook/config",
    response_model=WebhookTriggerConfig,
)
async def configure_webhook_trigger(
    workflow_id: UUID,
    request: WebhookTriggerConfig,
    repository: RepositoryDep,
) -> WebhookTriggerConfig:
    """Persist webhook trigger configuration for the workflow."""
    try:
        return await repository.configure_webhook_trigger(workflow_id, request)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.get(
    "/workflows/{workflow_id}/triggers/webhook/config",
    response_model=WebhookTriggerConfig,
)
async def get_webhook_trigger_config(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> WebhookTriggerConfig:
    """Return the configured webhook trigger definition."""
    try:
        return await repository.get_webhook_trigger_config(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.api_route(
    "/workflows/{workflow_id}/triggers/webhook",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    response_model=WorkflowRun,
    status_code=status.HTTP_202_ACCEPTED,
)
async def invoke_webhook_trigger(
    workflow_id: UUID,
    request: Request,
    repository: RepositoryDep,
    preserve_raw_body: bool = Query(
        default=False,
        description="Store the raw request body alongside parsed payloads.",
    ),
) -> WorkflowRun | JSONResponse:
    """Validate inbound webhook data and enqueue a workflow run."""
    try:
        raw_body = await request.body()
    except Exception as exc:  # pragma: no cover - FastAPI handles body read
        raise HTTPException(
            status_code=400,
            detail="Failed to read request body",
        ) from exc

    headers = {key: value for key, value in request.headers.items()}

    payload, parsed_body = _parse_webhook_body(
        raw_body, preserve_raw_body=preserve_raw_body
    )
    slack_response = _maybe_handle_slack_url_verification(parsed_body)
    if slack_response is not None:
        return slack_response

    try:
        client = request.client
        run = await repository.handle_webhook_trigger(
            workflow_id,
            method=request.method,
            headers=headers,
            query_params=dict(request.query_params),
            payload=payload,
            source_ip=getattr(client, "host", None),
        )
        return run
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        raise_not_found("Workflow version not found", exc)
    except WebhookValidationError as exc:
        raise_webhook_error(exc)
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc


@router.put(
    "/workflows/{workflow_id}/triggers/cron/config",
    response_model=CronTriggerConfig,
)
async def configure_cron_trigger(
    workflow_id: UUID,
    request: CronTriggerConfig,
    repository: RepositoryDep,
) -> CronTriggerConfig:
    """Persist cron trigger configuration for the workflow."""
    try:
        return await repository.configure_cron_trigger(workflow_id, request)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.get(
    "/workflows/{workflow_id}/triggers/cron/config",
    response_model=CronTriggerConfig,
)
async def get_cron_trigger_config(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> CronTriggerConfig:
    """Return the configured cron trigger definition."""
    try:
        return await repository.get_cron_trigger_config(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)


@router.delete(
    "/workflows/{workflow_id}/triggers/cron/config",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_cron_trigger(
    workflow_id: UUID,
    repository: RepositoryDep,
) -> Response:
    """Remove the cron trigger configuration for the workflow."""
    try:
        await repository.delete_cron_trigger(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/triggers/cron/dispatch",
    response_model=list[WorkflowRun],
)
async def dispatch_cron_triggers(
    repository: RepositoryDep,
    request: CronDispatchRequest | None = None,
) -> list[WorkflowRun]:
    """Evaluate cron schedules and enqueue any due runs."""
    now = request.now if request else None
    try:
        runs = await repository.dispatch_due_cron_runs(now=now)
        return runs
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc


@router.post(
    "/triggers/manual/dispatch",
    response_model=list[WorkflowRun],
)
async def dispatch_manual_runs(
    request: ManualDispatchRequest,
    repository: RepositoryDep,
) -> list[WorkflowRun]:
    """Dispatch one or more manual workflow runs."""
    try:
        runs = await repository.dispatch_manual_runs(request)
        return runs
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)
    except WorkflowVersionNotFoundError as exc:
        raise_not_found("Workflow version not found", exc)
    except CredentialHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": str(exc), "failures": exc.report.failures},
        ) from exc


__all__ = ["router"]
