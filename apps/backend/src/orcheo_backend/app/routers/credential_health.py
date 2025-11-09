"""Credential health routes."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, HTTPException, status
from orcheo.models import CredentialHealthStatus
from orcheo_backend.app.dependencies import (
    CredentialServiceDep,
    RepositoryDep,
)
from orcheo_backend.app.errors import raise_not_found
from orcheo_backend.app.history_utils import health_report_to_response
from orcheo_backend.app.repository import WorkflowNotFoundError
from orcheo_backend.app.schemas.credentials import (
    CredentialHealthResponse,
    CredentialValidationRequest,
)


router = APIRouter()


@router.get(
    "/workflows/{workflow_id}/credentials/health",
    response_model=CredentialHealthResponse,
)
async def get_workflow_credential_health(
    workflow_id: UUID,
    repository: RepositoryDep,
    service: CredentialServiceDep,
) -> CredentialHealthResponse:
    """Return cached credential health information for a workflow."""
    try:
        await repository.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential health service is not configured.",
        )

    report = service.get_report(workflow_id)
    if report is None:
        return CredentialHealthResponse(
            workflow_id=str(workflow_id),
            status=CredentialHealthStatus.UNKNOWN,
            checked_at=None,
            credentials=[],
        )
    return health_report_to_response(report)


@router.post(
    "/workflows/{workflow_id}/credentials/validate",
    response_model=CredentialHealthResponse,
)
async def validate_workflow_credentials(
    workflow_id: UUID,
    request: CredentialValidationRequest,
    repository: RepositoryDep,
    service: CredentialServiceDep,
) -> CredentialHealthResponse:
    """Trigger validation of workflow credentials and return the updated report."""
    try:
        await repository.get_workflow(workflow_id)
    except WorkflowNotFoundError as exc:
        raise_not_found("Workflow not found", exc)

    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Credential health service is not configured.",
        )

    report = await service.ensure_workflow_health(workflow_id, actor=request.actor)
    if not report.is_healthy:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "Credentials failed validation.",
                "failures": report.failures,
            },
        )
    return health_report_to_response(report)


__all__ = ["router"]
