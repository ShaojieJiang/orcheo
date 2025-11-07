"""Tests for ChatKit session token endpoint behaviour."""

from __future__ import annotations
from datetime import datetime
from typing import Any
from uuid import uuid4
import jwt
import pytest
from fastapi import HTTPException
from orcheo.models import CredentialHealthStatus
from orcheo.vault.oauth import (
    CredentialHealthError,
    CredentialHealthReport,
    CredentialHealthResult,
)
from orcheo_backend.app import create_chatkit_session_endpoint
from orcheo_backend.app.authentication import AuthorizationPolicy, RequestContext
from orcheo_backend.app.chatkit_tokens import (
    ChatKitSessionTokenIssuer,
    ChatKitTokenConfigurationError,
    ChatKitTokenSettings,
)
from orcheo_backend.app.schemas import ChatKitSessionRequest


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_returns_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ChatKit session endpoint returns a signed token for the caller."""

    monkeypatch.setenv("CHATKIT_TOKEN_SIGNING_KEY", "test-signing-key")

    policy = AuthorizationPolicy(
        RequestContext(
            subject="tester",
            identity_type="user",
            scopes=frozenset({"chatkit:session"}),
            workspace_ids=frozenset({"ws-1"}),
        )
    )
    issuer = ChatKitSessionTokenIssuer(
        ChatKitTokenSettings(
            signing_key="test-signing-key",
            issuer="test-issuer",
            audience="chatkit-client",
            ttl_seconds=120,
        )
    )
    request = ChatKitSessionRequest(workflow_id=None, metadata={})
    response = await create_chatkit_session_endpoint(
        request, policy=policy, issuer=issuer
    )

    decoded = jwt.decode(
        response.client_secret,
        "test-signing-key",
        algorithms=["HS256"],
        audience="chatkit-client",
        issuer="test-issuer",
    )
    assert decoded["sub"] == "tester"
    assert decoded["chatkit"]["workspace_id"] == "ws-1"
    assert decoded["chatkit"]["workflow_id"] is None


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_workflow_specific(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow-specific metadata should appear in the signed token."""

    monkeypatch.setenv("CHATKIT_TOKEN_SIGNING_KEY", "workflow-signing-key")

    policy = AuthorizationPolicy(
        RequestContext(
            subject="tester",
            identity_type="user",
            scopes=frozenset({"chatkit:session"}),
            workspace_ids=frozenset({"ws-2"}),
        )
    )
    issuer = ChatKitSessionTokenIssuer(
        ChatKitTokenSettings(
            signing_key="workflow-signing-key",
            issuer="workflow-issuer",
            audience="workflow-client",
            ttl_seconds=60,
        )
    )
    request = ChatKitSessionRequest(
        workflow_id=None,
        workflow_label="demo-workflow",
        metadata={"channel": "alpha"},
    )
    response = await create_chatkit_session_endpoint(
        request, policy=policy, issuer=issuer
    )

    decoded = jwt.decode(
        response.client_secret,
        "workflow-signing-key",
        algorithms=["HS256"],
        audience="workflow-client",
        issuer="workflow-issuer",
    )
    assert decoded["chatkit"]["workflow_label"] == "demo-workflow"
    assert decoded["chatkit"]["metadata"]["channel"] == "alpha"


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_missing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ChatKit session issuance raises a 503 when configuration is missing."""

    policy = AuthorizationPolicy(
        RequestContext(
            subject="tester",
            identity_type="user",
            scopes=frozenset({"chatkit:session"}),
            workspace_ids=frozenset({"ws-1"}),
        )
    )

    class FailingIssuer:
        def mint_session(self, **_: Any) -> tuple[str, datetime]:
            raise ChatKitTokenConfigurationError("ChatKit not configured")

    request = ChatKitSessionRequest(workflow_id=None)
    with pytest.raises(HTTPException) as exc_info:
        await create_chatkit_session_endpoint(
            request, policy=policy, issuer=FailingIssuer()
        )

    assert exc_info.value.status_code == 503
    assert "ChatKit not configured" in exc_info.value.detail["message"]


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_credential_health_error() -> None:
    """ChatKit session endpoint maps credential health failures to HTTP 503."""

    workflow_id = uuid4()
    report = CredentialHealthReport(
        workflow_id=workflow_id,
        results=[
            CredentialHealthResult(
                credential_id=uuid4(),
                name="slack",
                provider="slack",
                status=CredentialHealthStatus.UNHEALTHY,
                last_checked_at=datetime.now(),
                failure_reason="token expired",
            )
        ],
        checked_at=datetime.now(),
    )

    class UnhealthyIssuer:
        def mint_session(self, **_: Any) -> tuple[str, datetime]:
            raise CredentialHealthError(report)

    policy = AuthorizationPolicy(
        RequestContext(
            subject="tester",
            identity_type="user",
            scopes=frozenset({"chatkit:session"}),
            workspace_ids=frozenset({"ws-1"}),
        )
    )
    request = ChatKitSessionRequest(workflow_id=None)

    with pytest.raises(HTTPException) as exc_info:
        await create_chatkit_session_endpoint(
            request, policy=policy, issuer=UnhealthyIssuer()
        )

    assert exc_info.value.status_code == 503
    assert "unhealthy credentials" in exc_info.value.detail["message"].lower()


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_authentication_errors() -> None:
    """ChatKit session endpoint handles authentication errors properly."""

    issuer = ChatKitSessionTokenIssuer(
        ChatKitTokenSettings(
            signing_key="test-key",
            issuer="test-issuer",
            audience="test-audience",
            ttl_seconds=120,
        )
    )

    # Unauthenticated request
    policy = AuthorizationPolicy(
        RequestContext(
            subject="",
            identity_type="anonymous",
            scopes=frozenset(),
            workspace_ids=frozenset(),
        )
    )

    request = ChatKitSessionRequest(workflow_id=None)

    with pytest.raises(HTTPException) as exc_info:
        await create_chatkit_session_endpoint(request, policy=policy, issuer=issuer)

    assert exc_info.value.status_code in (401, 403)


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_workspace_error() -> None:
    """ChatKit session endpoint handles workspace authorization errors."""

    policy = AuthorizationPolicy(
        RequestContext(
            subject="test-user",
            identity_type="user",
            scopes=frozenset({"chatkit:session"}),
            workspace_ids=frozenset({"ws-allowed"}),
        )
    )

    issuer = ChatKitSessionTokenIssuer(
        ChatKitTokenSettings(
            signing_key="test-key",
            issuer="test-issuer",
            audience="test-audience",
            ttl_seconds=120,
        )
    )

    request = ChatKitSessionRequest(
        workflow_id=None,
        metadata={"workspace_id": "ws-different"},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_chatkit_session_endpoint(request, policy=policy, issuer=issuer)

    assert exc_info.value.status_code in (401, 403)


@pytest.mark.asyncio()
async def test_create_chatkit_session_endpoint_with_current_client_secret() -> None:
    """ChatKit session endpoint includes previous secret in extra payload."""

    policy = AuthorizationPolicy(
        RequestContext(
            subject="test-user",
            identity_type="user",
            scopes=frozenset({"chatkit:session"}),
            workspace_ids=frozenset({"ws-1"}),
        )
    )

    issuer = ChatKitSessionTokenIssuer(
        ChatKitTokenSettings(
            signing_key="test-key",
            issuer="test-issuer",
            audience="test-audience",
            ttl_seconds=120,
        )
    )

    request = ChatKitSessionRequest(
        workflow_id=None,
        metadata={},
        current_client_secret="old-secret-token",
    )

    response = await create_chatkit_session_endpoint(
        request, policy=policy, issuer=issuer
    )

    decoded = jwt.decode(
        response.client_secret,
        "test-key",
        algorithms=["HS256"],
        audience="test-audience",
        issuer="test-issuer",
    )
    assert "previous_secret" in decoded["chatkit"]
    assert decoded["chatkit"]["previous_secret"] == "old-secret-token"
