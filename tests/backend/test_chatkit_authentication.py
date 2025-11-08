"""Tests covering the ChatKit authentication helper."""

from __future__ import annotations
from typing import Any
import pytest
from starlette.requests import Request
from orcheo.models.workflow import generate_publish_token, hash_publish_token
from orcheo_backend.app.repository.in_memory import InMemoryWorkflowRepository
from tests.backend.api.shared import backend_app


async def _empty_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


def _make_request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/chatkit",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope, _empty_receive)


@pytest.fixture(autouse=True)
def reset_rate_limiters() -> None:
    backend_app.routers.chatkit._IP_RATE_LIMITER.reset()  # type: ignore[attr-defined]
    backend_app.routers.chatkit._JWT_RATE_LIMITER.reset()  # type: ignore[attr-defined]
    backend_app.routers.chatkit._PUBLISH_RATE_LIMITER.reset()  # type: ignore[attr-defined]
    backend_app.routers.chatkit._SESSION_RATE_LIMITER.reset()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_authenticate_chatkit_invocation_with_jwt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="JWT Workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    def mock_decode(_: str) -> dict[str, Any]:
        return {
            "sub": "alice",
            "chatkit": {"workflow_id": str(workflow.id), "token_id": "jwt-1"},
        }

    monkeypatch.setattr(backend_app.routers.chatkit, "_decode_chatkit_jwt", mock_decode)

    request = _make_request({"Authorization": "Bearer token"})
    result = await backend_app.routers.chatkit.authenticate_chatkit_invocation(
        request=request,
        payload={"workflow_id": str(workflow.id)},
        publish_token=None,
        repository=repository,
    )

    assert result.auth_mode == "jwt"
    assert result.actor == "jwt:alice"
    assert result.subject == "alice"


@pytest.mark.asyncio
async def test_authenticate_chatkit_invocation_with_publish_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Publish Workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    token = generate_publish_token()
    await repository.publish_workflow(
        workflow.id,
        publish_token_hash=hash_publish_token(token),
        require_login=False,
        actor="tester",
    )

    request = _make_request()
    result = await backend_app.routers.chatkit.authenticate_chatkit_invocation(
        request=request,
        payload={"workflow_id": str(workflow.id)},
        publish_token=token,
        repository=repository,
    )

    assert result.auth_mode == "publish"
    assert result.subject is None
    assert result.actor.startswith("publish:")


@pytest.mark.asyncio
async def test_authenticate_chatkit_requires_session_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = InMemoryWorkflowRepository()
    workflow = await repository.create_workflow(
        name="Protected Workflow",
        slug=None,
        description=None,
        tags=None,
        actor="tester",
    )

    token = generate_publish_token()
    await repository.publish_workflow(
        workflow.id,
        publish_token_hash=hash_publish_token(token),
        require_login=True,
        actor="tester",
    )

    request = _make_request()
    with pytest.raises(backend_app.routers.chatkit.HTTPException) as exc:
        await backend_app.routers.chatkit.authenticate_chatkit_invocation(
            request=request,
            payload={"workflow_id": str(workflow.id)},
            publish_token=token,
            repository=repository,
        )

    assert exc.value.status_code == 401

    session_request = _make_request({"X-Orcheo-OAuth-Subject": "bob"})
    result = await backend_app.routers.chatkit.authenticate_chatkit_invocation(
        request=session_request,
        payload={"workflow_id": str(workflow.id)},
        publish_token=token,
        repository=repository,
    )

    assert result.auth_mode == "publish"
    assert result.subject == "bob"
