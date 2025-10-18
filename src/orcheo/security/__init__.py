"""Automated security review helpers for workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Iterable
from uuid import UUID

from orcheo.models import (
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
)
from orcheo.triggers.layer import TriggerLayer
from orcheo.triggers.webhook import WebhookTriggerConfig
from orcheo.vault import BaseCredentialVault
from orcheo.vault.oauth import CredentialHealthGuard


@dataclass(slots=True)
class ReviewIssue:
    """Single security review finding."""

    message: str
    severity: str = "high"
    area: str | None = None


@dataclass(slots=True)
class SecurityReview:
    """Aggregated security review results for a workflow."""

    workflow_id: UUID
    checked_at: datetime
    issues: list[ReviewIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return ``True`` when no issues were raised."""

        return not self.issues

    def add_issue(self, message: str, *, severity: str = "high", area: str | None = None) -> None:
        """Append an issue to the review results."""

        self.issues.append(ReviewIssue(message=message, severity=severity, area=area))

    def extend(self, issues: Iterable[ReviewIssue]) -> None:
        """Append multiple issues to the review."""

        self.issues.extend(issues)

    def to_summary(self) -> str:
        """Return a human readable summary of the review."""

        status = "PASSED" if self.passed else "FAILED"
        header = f"Workflow {self.workflow_id} security review: {status}"
        if self.passed:
            return header
        lines = [header, "Findings:"]
        for issue in self.issues:
            scope = f" ({issue.area})" if issue.area else ""
            lines.append(f"- [{issue.severity}] {issue.message}{scope}")
        return "\n".join(lines)


def _review_credentials(
    review: SecurityReview,
    *,
    vault: BaseCredentialVault,
    workflow_id: UUID,
) -> None:
    """Inspect stored credentials for common security pitfalls."""

    context = CredentialAccessContext(workflow_id=workflow_id)
    for metadata in vault.list_credentials(context=context):
        if metadata.kind is CredentialKind.OAUTH:
            tokens = metadata.reveal_oauth_tokens(cipher=vault.cipher)
            if tokens is None:
                review.add_issue(
                    f"Credential {metadata.name} for provider {metadata.provider} is missing OAuth tokens",
                    area="credentials",
                    severity="critical",
                )
            elif not tokens.refresh_token:
                review.add_issue(
                    (
                        f"Credential {metadata.name} for provider {metadata.provider} "
                        "is missing refresh token support; configure OAuth refresh to avoid downtime"
                    ),
                    area="credentials",
                )
        if metadata.health.status is CredentialHealthStatus.UNHEALTHY:
            reason = metadata.health.failure_reason or "no failure reason provided"
            review.add_issue(
                (
                    f"Credential {metadata.name} reported unhealthy state "
                    f"({reason}). Regenerate secrets before enabling automations"
                ),
                area="credentials",
            )


def _review_webhook_triggers(
    review: SecurityReview,
    *,
    triggers: TriggerLayer,
    workflow_id: UUID,
) -> None:
    """Validate webhook configuration for common hardening gaps."""

    config: WebhookTriggerConfig = triggers.get_webhook_config(workflow_id)
    if config.shared_secret is None or config.shared_secret_header is None:
        review.add_issue(
            (
                "Webhook trigger is missing shared secret authentication. "
                "Define a secret header/value pair to prevent replay attacks"
            ),
            area="webhook",
            severity="medium",
        )
    if not config.allowed_methods:
        review.add_issue(
            "Webhook trigger allows no HTTP methods; requests will always fail",
            area="webhook",
            severity="low",
        )


def run_security_review(
    *,
    workflow_id: UUID,
    vault: BaseCredentialVault,
    triggers: TriggerLayer,
    health_guard: CredentialHealthGuard | None = None,
) -> SecurityReview:
    """Execute a synchronous security review for the provided workflow."""

    review = SecurityReview(workflow_id=workflow_id, checked_at=datetime.now(tz=UTC))
    _review_credentials(review, vault=vault, workflow_id=workflow_id)
    _review_webhook_triggers(review, triggers=triggers, workflow_id=workflow_id)
    if health_guard and not health_guard.is_workflow_healthy(workflow_id):
        report = health_guard.get_report(workflow_id)
        if report is not None:
            for failure in report.failures:
                review.add_issue(
                    f"Credential health guard reported failure: {failure}",
                    area="credentials",
                )
    return review


__all__ = ["ReviewIssue", "SecurityReview", "run_security_review"]
