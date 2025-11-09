"""Coverage for the workflow-scoped ChatKit session endpoint."""

from __future__ import annotations
from uuid import UUID, uuid4
import jwt
import pytest
from fastapi import HTTPException
from orcheo.models.workflow import Workflow
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthorizationError,
    AuthorizationPolicy,
    RequestContext,
)
from orcheo_backend.app.chatkit_tokens import (
    ChatKitSessionTokenIssuer,
    ChatKitTokenSettings,
)
from orcheo_backend.app.repository import WorkflowNotFoundError
from orcheo_backend.app.routers import workflows


class _WorkflowRepo:
    def __init__(self, workflow: Workflow) -> None:
        self._workflow = workflow

    async def get_workflow(self, workflow_id: UUID) -> Workflow:
        if workflow_id != self._workflow.id:
            raise WorkflowNotFoundError(str(workflow_id))
        return self._workflow


class _MissingWorkflowRepo:
    async def get_workflow(self, workflow_id: UUID) -> Workflow:
        raise WorkflowNotFoundError(str(workflow_id))


def _issuer() -> ChatKitSessionTokenIssuer:
    return ChatKitSessionTokenIssuer(
        ChatKitTokenSettings(
            signing_key="canvas-chatkit-key",
            issuer="canvas-backend",
            audience="chatkit-client",
            ttl_seconds=300,
        )
    )


def _policy(scopes: set[str]) -> AuthorizationPolicy:
    context = RequestContext(
        subject="canvas-user",
        identity_type="user",
        scopes=frozenset(scopes),
        workspace_ids=frozenset({"ws-1"}),
    )
    return AuthorizationPolicy(context)


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_requires_authentication() -> None:
    workflow = Workflow(name="Canvas Workflow", tags=["workspace:ws-1"])
    repo = _WorkflowRepo(workflow)
    policy = AuthorizationPolicy(RequestContext.anonymous())

    with pytest.raises(AuthenticationError):
        await workflows.create_workflow_chatkit_session(
            workflow.id,
            repo,
            policy=policy,
            issuer=_issuer(),
        )


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_requires_permissions() -> None:
    workflow = Workflow(name="Canvas Workflow", tags=["workspace:ws-1"])
    repo = _WorkflowRepo(workflow)
    policy = _policy({"workflows:read"})  # missing execute scope

    with pytest.raises(AuthorizationError):
        await workflows.create_workflow_chatkit_session(
            workflow.id,
            repo,
            policy=policy,
            issuer=_issuer(),
        )


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_validates_workflow_exists() -> None:
    repo = _MissingWorkflowRepo()
    policy = _policy({"workflows:read", "workflows:execute"})

    with pytest.raises(HTTPException) as excinfo:
        await workflows.create_workflow_chatkit_session(
            uuid4(),
            repo,
            policy=policy,
            issuer=_issuer(),
        )

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_mints_scoped_token() -> None:
    workflow = Workflow(name="Canvas Workflow", tags=["workspace:ws-1"])
    repo = _WorkflowRepo(workflow)
    policy = _policy({"workflows:read", "workflows:execute"})
    issuer = _issuer()

    response = await workflows.create_workflow_chatkit_session(
        workflow.id,
        repo,
        policy=policy,
        issuer=issuer,
    )

    decoded = jwt.decode(
        response.client_secret,
        "canvas-chatkit-key",
        algorithms=["HS256"],
        audience="chatkit-client",
        issuer="canvas-backend",
    )

    assert decoded["sub"] == "canvas-user"
    assert decoded["chatkit"]["workflow_id"] == str(workflow.id)
    assert decoded["chatkit"]["workspace_id"] == "ws-1"
    assert decoded["chatkit"]["metadata"]["workflow_name"] == "Canvas Workflow"
    assert decoded["chatkit"]["metadata"]["source"] == "canvas"
    assert decoded["chatkit"]["interface"] == "canvas_modal"


def test_select_primary_workspace_handles_multiple_workspaces() -> None:
    workspace_ids = frozenset({"ws-1", "ws-2"})

    assert workflows._select_primary_workspace(workspace_ids) is None


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_requires_workspace_match() -> None:
    workflow = Workflow(name="Canvas Workflow", tags=["workspace:ws-allowed"])
    repo = _WorkflowRepo(workflow)
    policy = AuthorizationPolicy(
        RequestContext(
            subject="canvas-user",
            identity_type="user",
            scopes=frozenset({"workflows:read", "workflows:execute"}),
            workspace_ids=frozenset({"ws-denied"}),
        )
    )

    with pytest.raises(AuthorizationError):
        await workflows.create_workflow_chatkit_session(
            workflow.id,
            repo,
            policy=policy,
            issuer=_issuer(),
        )


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_falls_back_to_owner() -> None:
    workflow = Workflow(name="Canvas Workflow")
    workflow.record_event(actor="canvas-user", action="workflow_created")
    repo = _WorkflowRepo(workflow)
    policy = AuthorizationPolicy(
        RequestContext(
            subject="canvas-user",
            identity_type="user",
            scopes=frozenset({"workflows:read", "workflows:execute"}),
            workspace_ids=frozenset(),
        )
    )

    response = await workflows.create_workflow_chatkit_session(
        workflow.id,
        repo,
        policy=policy,
        issuer=_issuer(),
    )

    decoded = jwt.decode(
        response.client_secret,
        "canvas-chatkit-key",
        algorithms=["HS256"],
        audience="chatkit-client",
        issuer="canvas-backend",
    )

    assert decoded["chatkit"]["workflow_id"] == str(workflow.id)


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_requires_workspace_access_for_tagged_workflows() -> (  # noqa: E501
    None
):
    workflow = Workflow(name="Canvas Workflow", tags=["workspace:ws-1"])
    repo = _WorkflowRepo(workflow)
    policy = AuthorizationPolicy(
        RequestContext(
            subject="canvas-user",
            identity_type="user",
            scopes=frozenset({"workflows:read", "workflows:execute"}),
            workspace_ids=frozenset(),
        )
    )

    with pytest.raises(AuthorizationError) as excinfo:
        await workflows.create_workflow_chatkit_session(
            workflow.id,
            repo,
            policy=policy,
            issuer=_issuer(),
        )

    assert excinfo.value.code == "auth.workspace_forbidden"


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_denies_when_owner_mismatch() -> None:
    workflow = Workflow(name="Canvas Workflow")
    workflow.record_event(actor="canvas-owner", action="workflow_created")
    repo = _WorkflowRepo(workflow)
    policy = AuthorizationPolicy(
        RequestContext(
            subject="another-user",
            identity_type="user",
            scopes=frozenset({"workflows:read", "workflows:execute"}),
            workspace_ids=frozenset(),
        )
    )

    with pytest.raises(AuthorizationError) as excinfo:
        await workflows.create_workflow_chatkit_session(
            workflow.id,
            repo,
            policy=policy,
            issuer=_issuer(),
        )

    assert excinfo.value.code == "auth.forbidden"


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_allows_developer_owner_mismatch() -> (
    None
):
    workflow = Workflow(name="Canvas Workflow")
    workflow.record_event(actor="cli", action="workflow_created")
    repo = _WorkflowRepo(workflow)
    policy = AuthorizationPolicy(
        RequestContext(
            subject="dev:local-user",
            identity_type="developer",
            scopes=frozenset({"workflows:read", "workflows:execute"}),
            workspace_ids=frozenset(),
        )
    )

    response = await workflows.create_workflow_chatkit_session(
        workflow.id,
        repo,
        policy=policy,
        issuer=_issuer(),
    )

    decoded = jwt.decode(
        response.client_secret,
        "canvas-chatkit-key",
        algorithms=["HS256"],
        audience="chatkit-client",
        issuer="canvas-backend",
    )

    assert decoded["chatkit"]["workflow_id"] == str(workflow.id)


@pytest.mark.asyncio()
async def test_create_workflow_chatkit_session_allows_ownerless_workflow() -> None:
    workflow = Workflow(name="Canvas Workflow")
    repo = _WorkflowRepo(workflow)
    policy = AuthorizationPolicy(
        RequestContext(
            subject="canvas-user",
            identity_type="user",
            scopes=frozenset({"workflows:read", "workflows:execute"}),
            workspace_ids=frozenset(),
        )
    )

    response = await workflows.create_workflow_chatkit_session(
        workflow.id,
        repo,
        policy=policy,
        issuer=_issuer(),
    )

    decoded = jwt.decode(
        response.client_secret,
        "canvas-chatkit-key",
        algorithms=["HS256"],
        audience="chatkit-client",
        issuer="canvas-backend",
    )

    assert decoded["chatkit"]["workflow_id"] == str(workflow.id)
