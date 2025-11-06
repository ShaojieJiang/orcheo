from __future__ import annotations
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
import pytest
from fastapi import HTTPException
from orcheo.vault import InMemoryCredentialVault, WorkflowScopeError
from orcheo_backend.app.schemas import (
    CredentialIssuancePolicyPayload,
    CredentialScopePayload,
    OAuthTokenRequest,
)
from .shared import backend_app


def test_backend_helper_builders_and_scope_errors() -> None:
    scope_payload = CredentialScopePayload(
        workflow_ids=[uuid4()],
        workspace_ids=[uuid4()],
        roles=["admin"],
    )
    scope = backend_app._build_scope(scope_payload)
    assert scope.workflow_ids

    assert backend_app._build_scope(None) is None

    policy_payload = CredentialIssuancePolicyPayload(
        require_refresh_token=True,
        rotation_period_days=7,
        expiry_threshold_minutes=30,
    )
    policy = backend_app._build_policy(policy_payload)
    assert policy.require_refresh_token is True

    token_payload = OAuthTokenRequest(
        access_token="a", refresh_token="b", expires_at=datetime.now(tz=UTC)
    )
    tokens = backend_app._build_oauth_tokens(token_payload)
    assert tokens.refresh_token == "b"
    assert backend_app._build_oauth_tokens(None) is None

    workflow_id = uuid4()
    context = backend_app._context_from_workflow(workflow_id)
    assert context is not None and context.workflow_id == workflow_id
    assert backend_app._context_from_workflow(None) is None

    with pytest.raises(HTTPException) as excinfo:
        backend_app._raise_scope_error(WorkflowScopeError("denied"))
    assert excinfo.value.status_code == 403


def test_get_vault_initializes_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    created: dict[str, bool] = {}

    def fake_create(settings: Any) -> InMemoryCredentialVault:
        created["called"] = True
        return InMemoryCredentialVault()

    monkeypatch.setitem(backend_app._vault_ref, "vault", None)
    monkeypatch.setitem(backend_app._credential_service_ref, "service", None)
    monkeypatch.setattr(backend_app, "_create_vault", fake_create)
    monkeypatch.setattr(backend_app, "get_settings", lambda: object())

    vault = backend_app.get_vault()

    assert created == {"called": True}
    assert isinstance(vault, InMemoryCredentialVault)
