"""Workflow trigger routes."""

from __future__ import annotations
import json
from typing import Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, status
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


router = APIRouter()


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
) -> WorkflowRun:
    """Validate inbound webhook data and enqueue a workflow run."""
    try:
        raw_body = await request.body()
    except Exception as exc:  # pragma: no cover - FastAPI handles body read
        raise HTTPException(
            status_code=400,
            detail="Failed to read request body",
        ) from exc

    payload: Any
    if raw_body:
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = raw_body
    else:
        payload = {}

    headers = {key: value for key, value in request.headers.items()}

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
        return await repository.dispatch_due_cron_runs(now=now)
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
        return await repository.dispatch_manual_runs(request)
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
