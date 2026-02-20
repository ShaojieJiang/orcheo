"""Tests for credential CRUD endpoints."""

from __future__ import annotations
from datetime import UTC, datetime
from uuid import uuid4
import pytest
from fastapi import HTTPException
from orcheo.models import CredentialKind, CredentialMetadata, CredentialScope
from orcheo.vault import (
    CredentialNotFoundError,
    DuplicateCredentialNameError,
    WorkflowScopeError,
)


def test_list_credentials_success() -> None:
    """List credentials endpoint returns credentials."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import list_credentials

    cred1_id = uuid4()
    cred2_id = uuid4()

    class Vault:
        def list_credentials(self, context=None):
            return [
                CredentialMetadata(
                    id=cred1_id,
                    name="Cred 1",
                    provider="slack",
                    kind=CredentialKind.OAUTH,
                    scope=CredentialScope(),
                    encryption=EncryptionEnvelope(
                        algorithm="aes-256-gcm",
                        key_id="test-key",
                        ciphertext="encrypted",
                    ),
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
                CredentialMetadata(
                    id=cred2_id,
                    name="Cred 2",
                    provider="github",
                    kind=CredentialKind.SECRET,
                    scope=CredentialScope(),
                    encryption=EncryptionEnvelope(
                        algorithm="aes-256-gcm",
                        key_id="test-key",
                        ciphertext="encrypted",
                    ),
                    created_at=datetime.now(tz=UTC),
                    updated_at=datetime.now(tz=UTC),
                ),
            ]

    result = list_credentials(Vault())

    assert len(result) == 2
    assert result[0].id == str(cred1_id)
    assert result[1].id == str(cred2_id)


def test_list_credentials_with_workflow_context() -> None:
    """List credentials uses workflow context for filtering."""
    from orcheo_backend.app import list_credentials

    workflow_id = uuid4()
    context_received = None

    class Vault:
        def list_credentials(self, context=None):
            nonlocal context_received
            context_received = context
            return []

    list_credentials(Vault(), workflow_id=workflow_id)

    assert context_received is not None
    assert context_received.workflow_id == workflow_id


def test_create_credential_success() -> None:
    """Create credential endpoint creates and returns credential."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import create_credential
    from orcheo_backend.app.schemas.credentials import CredentialCreateRequest

    cred_id = uuid4()

    class Vault:
        def create_credential(self, name, provider, scopes, secret, actor, scope, kind):
            return CredentialMetadata(
                id=cred_id,
                name=name,
                provider=provider,
                kind=kind,
                scope=scope or CredentialScope(),
                encryption=EncryptionEnvelope(
                    algorithm="aes-256-gcm",
                    key_id="test-key",
                    ciphertext="encrypted",
                ),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = CredentialCreateRequest(
        name="Test Cred",
        provider="slack",
        scopes=["chat:write"],
        secret="test-secret",
        actor="user",
        access="public",
        kind=CredentialKind.SECRET,
    )

    result = create_credential(request, Vault())

    assert result.id == str(cred_id)
    assert result.name == "Test Cred"


def test_create_credential_validation_error() -> None:
    """Create credential handles validation errors."""
    from orcheo_backend.app import create_credential
    from orcheo_backend.app.schemas.credentials import CredentialCreateRequest

    class Vault:
        def create_credential(self, name, provider, scopes, secret, actor, scope, kind):
            raise ValueError("Invalid credential")

    request = CredentialCreateRequest(
        name="Test Cred",
        provider="slack",
        scopes=[],
        secret="test-secret",
        actor="user",
        access="public",
        kind=CredentialKind.SECRET,
    )

    with pytest.raises(HTTPException) as exc_info:
        create_credential(request, Vault())

    assert exc_info.value.status_code == 422


def test_create_credential_access_override() -> None:
    """Create credential overrides access when request differs from inferred."""
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import create_credential
    from orcheo_backend.app.schemas.credentials import CredentialCreateRequest

    cred_id = uuid4()
    workflow_id = uuid4()

    class Vault:
        def create_credential(self, name, provider, scopes, secret, actor, scope, kind):
            return CredentialMetadata(
                id=cred_id,
                name=name,
                provider=provider,
                kind=kind,
                scope=CredentialScope(workflow_ids=[workflow_id]),
                encryption=EncryptionEnvelope(
                    algorithm="aes-256-gcm",
                    key_id="test-key",
                    ciphertext="encrypted",
                ),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = CredentialCreateRequest(
        name="Test Cred",
        provider="slack",
        scopes=["chat:write"],
        secret="test-secret",
        actor="user",
        access="shared",
        kind=CredentialKind.SECRET,
    )

    result = create_credential(request, Vault())

    assert result.access == "shared"


def test_delete_credential_success() -> None:
    """Delete credential endpoint deletes credential."""
    from orcheo_backend.app import delete_credential

    cred_id = uuid4()
    deleted_id = None

    class Vault:
        def delete_credential(self, credential_id, context=None):
            nonlocal deleted_id
            deleted_id = credential_id

    response = delete_credential(cred_id, Vault())

    assert response.status_code == 204
    assert deleted_id == cred_id


def test_delete_credential_not_found() -> None:
    """Delete credential raises 404 for missing credential."""
    from orcheo.vault import CredentialNotFoundError
    from orcheo_backend.app import delete_credential

    cred_id = uuid4()

    class Vault:
        def delete_credential(self, credential_id, context=None):
            raise CredentialNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        delete_credential(cred_id, Vault())

    assert exc_info.value.status_code == 404


def test_delete_credential_scope_error() -> None:
    """Delete credential raises 403 for scope violations."""
    from orcheo_backend.app import delete_credential

    cred_id = uuid4()

    class Vault:
        def delete_credential(self, credential_id, context=None):
            raise WorkflowScopeError("Access denied")

    with pytest.raises(HTTPException) as exc_info:
        delete_credential(cred_id, Vault())

    assert exc_info.value.status_code == 403


def test_reveal_credential_secret_not_found() -> None:
    from orcheo_backend.app import reveal_credential_secret

    cred_id = uuid4()

    class Vault:
        def reveal_secret(self, credential_id, context=None):
            raise CredentialNotFoundError("not found")

    with pytest.raises(HTTPException) as exc_info:
        reveal_credential_secret(cred_id, Vault())

    assert exc_info.value.status_code == 404


def test_reveal_credential_secret_scope_error() -> None:
    from orcheo_backend.app import reveal_credential_secret

    cred_id = uuid4()

    class Vault:
        def reveal_secret(self, credential_id, context=None):
            raise WorkflowScopeError("denied")

    with pytest.raises(HTTPException) as exc_info:
        reveal_credential_secret(cred_id, Vault())

    assert exc_info.value.status_code == 403


def test_update_credential_duplicate_name_error() -> None:
    from orcheo_backend.app import update_credential
    from orcheo_backend.app.schemas.credentials import CredentialUpdateRequest

    cred_id = uuid4()

    class Vault:
        def update_credential(self, **kwargs):
            raise DuplicateCredentialNameError("name already in use")

    request = CredentialUpdateRequest(actor="tester", name="duplicate")
    with pytest.raises(HTTPException) as exc_info:
        update_credential(cred_id, request, Vault())

    assert exc_info.value.status_code == 409


def test_update_credential_validation_error() -> None:
    from orcheo_backend.app import update_credential
    from orcheo_backend.app.schemas.credentials import CredentialUpdateRequest

    cred_id = uuid4()

    class Vault:
        def update_credential(self, **kwargs):
            raise ValueError("invalid")

    request = CredentialUpdateRequest(actor="tester", name="bad")
    with pytest.raises(HTTPException) as exc_info:
        update_credential(cred_id, request, Vault())

    assert exc_info.value.status_code == 422


def test_update_credential_access_override() -> None:
    from orcheo.models import EncryptionEnvelope
    from orcheo_backend.app import update_credential
    from orcheo_backend.app.schemas.credentials import CredentialUpdateRequest

    cred_id = uuid4()
    workflow_id = uuid4()

    class Vault:
        def update_credential(self, **kwargs):
            return CredentialMetadata(
                id=cred_id,
                name="Updated",
                provider="api",
                kind=CredentialKind.SECRET,
                scope=CredentialScope(workflow_ids=[workflow_id]),
                encryption=EncryptionEnvelope(
                    algorithm="aes-256-gcm",
                    key_id="test-key",
                    ciphertext="encrypted",
                ),
                created_at=datetime.now(tz=UTC),
                updated_at=datetime.now(tz=UTC),
            )

    request = CredentialUpdateRequest(actor="tester", access="shared")
    result = update_credential(cred_id, request, Vault(), workflow_id=workflow_id)
    assert result.access == "shared"
