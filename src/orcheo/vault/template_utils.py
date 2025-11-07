"""Utility helpers for updating credential template fields."""

from __future__ import annotations
from collections.abc import Sequence
from orcheo.models import (
    CredentialIssuancePolicy,
    CredentialKind,
    CredentialScope,
    CredentialTemplate,
)


def update_template_simple_field(
    template: CredentialTemplate,
    attr: str,
    value: str | None,
    changes: dict[str, object],
) -> None:
    """Update a template scalar field while recording change metadata."""
    if value is None:
        return
    current = getattr(template, attr)
    if current == value:
        return
    changes[attr] = {"from": current, "to": value}
    setattr(template, attr, value)


def update_template_scopes(
    template: CredentialTemplate,
    scopes: Sequence[str] | None,
    changes: dict[str, object],
) -> None:
    """Update template scopes while tracking original values."""
    if scopes is None:
        return
    normalized = list(scopes)
    if normalized == template.scopes:
        return
    changes["scopes"] = {
        "from": list(template.scopes),
        "to": normalized,
    }
    template.scopes = normalized


def update_template_scope(
    template: CredentialTemplate,
    scope: CredentialScope | None,
    changes: dict[str, object],
) -> None:
    """Update the template scope and record the diff."""
    if scope is None or scope == template.scope:
        return
    changes["scope"] = {
        "from": template.scope.model_dump(),
        "to": scope.model_dump(),
    }
    template.scope = scope


def normalize_template_kind(
    kind: CredentialKind | str | None,
) -> CredentialKind | None:
    """Normalize user-provided template kind values to the enum."""
    if kind is None:
        return None
    if isinstance(kind, CredentialKind):
        return kind
    return CredentialKind(str(kind))


def update_template_kind(
    template: CredentialTemplate,
    kind: CredentialKind | str | None,
    changes: dict[str, object],
) -> None:
    """Update the template's credential kind when it changes."""
    new_kind = normalize_template_kind(kind)
    if new_kind is None or new_kind is template.kind:
        return
    changes["kind"] = {
        "from": template.kind.value,
        "to": new_kind.value,
    }
    template.kind = new_kind


def update_template_policy(
    template: CredentialTemplate,
    issuance_policy: CredentialIssuancePolicy | None,
    changes: dict[str, object],
) -> None:
    """Update the template issuance policy when a new value is provided."""
    if issuance_policy is None:
        return
    if issuance_policy.model_dump() == template.issuance_policy.model_dump():
        return
    changes["issuance_policy"] = {
        "from": template.issuance_policy.model_dump(),
        "to": issuance_policy.model_dump(),
    }
    template.issuance_policy = issuance_policy


__all__ = [
    "normalize_template_kind",
    "update_template_kind",
    "update_template_policy",
    "update_template_scope",
    "update_template_scopes",
    "update_template_simple_field",
]
