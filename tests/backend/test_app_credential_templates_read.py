"""Tests for reading credential templates."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from orcheo.models import CredentialKind, CredentialScope
from orcheo.vault import WorkflowScopeError


def test_list_credential_templates_success() -> None:
    """List credential templates endpoint returns templates."""
    from orcheo.models import CredentialIssuancePolicy, CredentialTemplate
    from orcheo_backend.app import list_credential_templates

    template1_id = uuid4()
    template2_id = uuid4()

    class Vault:
        def list_templates(self, context=None):
            return [
                CredentialTemplate(
                    id=template1_id,
                    name="Template 1",
                    provider="slack",
                    scopes=["chat:write"],
                    kind=CredentialKind.OAUTH,
                    scope=CredentialScope(),
                    issuance_policy=CredentialIssuancePolicy(),
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
                CredentialTemplate(
                    id=template2_id,
                    name="Template 2",
                    provider="github",
                    scopes=["repo"],
                    kind=CredentialKind.OAUTH,
                    scope=CredentialScope(),
                    issuance_policy=CredentialIssuancePolicy(),
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
            ]

    result = list_credential_templates(Vault())

    assert len(result) == 2
    assert result[0].id == str(template1_id)
    assert result[1].id == str(template2_id)


def test_get_credential_template_success() -> None:
    """Get credential template endpoint returns template."""
    from orcheo.models import CredentialIssuancePolicy, CredentialTemplate
    from orcheo_backend.app import get_credential_template

    template_id = uuid4()

    class Vault:
        def get_template(self, template_id, context=None):
            return CredentialTemplate(
                id=template_id,
                name="Test Template",
                provider="slack",
                scopes=["chat:write"],
                kind=CredentialKind.OAUTH,
                scope=CredentialScope(),
                issuance_policy=CredentialIssuancePolicy(),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    result = get_credential_template(template_id, Vault())

    assert result.id == str(template_id)


def test_get_credential_template_not_found() -> None:
    """Get credential template raises 404 for missing template."""
    from orcheo.vault import CredentialTemplateNotFoundError
    from orcheo_backend.app import get_credential_template

    template_id = uuid4()

    class Vault:
        def get_template(self, template_id, context=None):
            raise CredentialTemplateNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        get_credential_template(template_id, Vault())

    assert exc_info.value.status_code == 404


def test_get_credential_template_scope_error() -> None:
    """Get credential template raises 403 for scope violations."""
    from orcheo_backend.app import get_credential_template

    template_id = uuid4()

    class Vault:
        def get_template(self, template_id, context=None):
            raise WorkflowScopeError("Access denied")

    with pytest.raises(HTTPException) as exc_info:
        get_credential_template(template_id, Vault())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Access denied"
