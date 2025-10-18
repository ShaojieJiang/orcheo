"""Backend helpers for credential templates and governance alerts."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from orcheo.models import CredentialAccessContext
from orcheo.vault import BaseCredentialVault, build_default_registry
from orcheo.vault.templates import (
    SecretGovernanceAlert,
    TemplateRegistry,
)


@dataclass(slots=True)
class TemplateService:
    """Service coordinating template registry with governance alerts."""

    vault: BaseCredentialVault
    registry: TemplateRegistry

    def list_templates(self) -> list[dict[str, Any]]:
        """Return templates serialised for API responses."""
        return [
            {
                "slug": template.slug,
                "name": template.name,
                "provider": template.provider,
                "description": template.description,
                "scopes": list(template.scopes),
                "rotation_days": template.rotation_days,
                "fields": [
                    {
                        "key": field.key,
                        "label": field.label,
                        "description": field.description,
                        "required": field.required,
                        "secret": field.secret,
                        "default": field.default,
                    }
                    for field in template.fields
                ],
            }
            for template in self.registry.list()
        ]

    def issue_from_template(
        self,
        slug: str,
        *,
        actor: str,
        workflow_id: UUID | None,
        payload: dict[str, str],
    ) -> dict[str, Any]:
        """Materialise the credential and return masked metadata."""
        metadata = self.registry.issue_from_template(
            slug,
            vault=self.vault,
            actor=actor,
            workflow_id=workflow_id,
            payload=payload,
        )
        return dict(metadata.redact())

    def evaluate_governance(self, *, workflow_id: UUID) -> list[dict[str, Any]]:
        """Return governance alerts for the workflow."""
        alerts: list[SecretGovernanceAlert] = (
            self.registry.evaluate_workflow_governance(
                vault=self.vault,
                workflow_id=workflow_id,
                context=CredentialAccessContext(workflow_id=workflow_id),
            )
        )
        return [_serialize_alert(alert) for alert in alerts]


def _serialize_alert(alert: SecretGovernanceAlert) -> dict[str, Any]:
    return {
        "credential_id": str(alert.credential_id),
        "kind": alert.kind,
        "level": alert.level,
        "message": alert.message,
    }


def build_template_service(vault: BaseCredentialVault) -> TemplateService:
    """Build a TemplateService backed by the default registry."""
    registry = build_default_registry()
    return TemplateService(vault=vault, registry=registry)


__all__ = [
    "TemplateService",
    "build_template_service",
]
