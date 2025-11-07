"""Credential governance alert routes."""

from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter
from orcheo.vault import GovernanceAlertNotFoundError, WorkflowScopeError
from orcheo_backend.app.credential_utils import alert_to_response
from orcheo_backend.app.dependencies import (
    IncludeAcknowledgedQuery,
    VaultDep,
    WorkflowIdQuery,
    credential_context_from_workflow,
)
from orcheo_backend.app.errors import raise_not_found, raise_scope_error
from orcheo_backend.app.schemas import (
    AlertAcknowledgeRequest,
    GovernanceAlertResponse,
)


router = APIRouter()


@router.get(
    "/credentials/governance-alerts",
    response_model=list[GovernanceAlertResponse],
)
def list_governance_alerts(
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
    include_acknowledged: IncludeAcknowledgedQuery = False,
) -> list[GovernanceAlertResponse]:
    """List governance alerts for the caller."""
    context = credential_context_from_workflow(workflow_id)
    alerts = vault.list_alerts(
        context=context,
        include_acknowledged=include_acknowledged,
    )
    return [alert_to_response(alert) for alert in alerts]


@router.post(
    "/credentials/governance-alerts/{alert_id}/acknowledge",
    response_model=GovernanceAlertResponse,
)
def acknowledge_governance_alert(
    alert_id: UUID,
    request: AlertAcknowledgeRequest,
    vault: VaultDep,
    workflow_id: WorkflowIdQuery = None,
) -> GovernanceAlertResponse:
    """Acknowledge an outstanding governance alert."""
    context = credential_context_from_workflow(workflow_id)
    try:
        alert = vault.acknowledge_alert(alert_id, actor=request.actor, context=context)
        return alert_to_response(alert)
    except GovernanceAlertNotFoundError as exc:
        raise_not_found("Governance alert not found", exc)
    except WorkflowScopeError as exc:
        raise_scope_error(exc)


__all__ = ["router"]
