"""Helpers for converting run history data into API responses."""

from __future__ import annotations
from orcheo.models import CredentialHealthStatus
from orcheo.vault.oauth import CredentialHealthReport
from orcheo_backend.app.history import RunHistoryRecord
from orcheo_backend.app.schemas.credentials import (
    CredentialHealthItem,
    CredentialHealthResponse,
)
from orcheo_backend.app.schemas.runs import (
    RunHistoryResponse,
    RunHistoryStepResponse,
)


def history_to_response(
    record: RunHistoryRecord,
    *,
    from_step: int = 0,
) -> RunHistoryResponse:
    """Convert a history record into a serialisable response."""
    steps = [
        RunHistoryStepResponse(
            index=step.index,
            at=step.at,
            payload=step.payload,
        )
        for step in record.steps[from_step:]
    ]
    return RunHistoryResponse(
        execution_id=record.execution_id,
        workflow_id=record.workflow_id,
        status=record.status,
        started_at=record.started_at,
        completed_at=record.completed_at,
        error=record.error,
        inputs=record.inputs,
        steps=steps,
    )


def health_report_to_response(
    report: CredentialHealthReport,
) -> CredentialHealthResponse:
    """Convert a credential health report into a response payload."""
    credentials = [
        CredentialHealthItem(
            credential_id=str(result.credential_id),
            name=result.name,
            provider=result.provider,
            status=result.status,
            last_checked_at=result.last_checked_at,
            failure_reason=result.failure_reason,
        )
        for result in report.results
    ]
    overall_status = (
        CredentialHealthStatus.HEALTHY
        if report.is_healthy
        else CredentialHealthStatus.UNHEALTHY
    )
    return CredentialHealthResponse(
        workflow_id=str(report.workflow_id),
        status=overall_status,
        checked_at=report.checked_at,
        credentials=credentials,
    )


__all__ = ["health_report_to_response", "history_to_response"]
