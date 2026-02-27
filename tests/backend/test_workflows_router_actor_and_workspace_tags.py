"""Tests for workflow actor and workspace tag resolution in router handlers."""

from __future__ import annotations
from types import SimpleNamespace
import pytest
from orcheo.models.workflow import Workflow
from orcheo_backend.app.authentication import AuthorizationPolicy, RequestContext
from orcheo_backend.app.routers import workflows
from orcheo_backend.app.schemas.workflows import (
    WorkflowCreateRequest,
    WorkflowUpdateRequest,
)


class _Repository:
    def __init__(self) -> None:
        self.last_actor: str | None = None
        self.last_tags: list[str] | None = None

    async def create_workflow(
        self,
        *,
        name: str,
        slug: str | None,
        description: str | None,
        tags: list[str] | None,
        actor: str,
    ) -> Workflow:
        self.last_actor = actor
        self.last_tags = list(tags or [])
        return Workflow(
            name=name, slug=slug or "", description=description, tags=tags or []
        )

    async def update_workflow(
        self,
        workflow_id,
        *,
        name: str | None,
        description: str | None,
        tags: list[str] | None,
        is_archived: bool | None,
        actor: str,
    ) -> Workflow:
        self.last_actor = actor
        self.last_tags = list(tags) if tags is not None else None
        return Workflow(
            id=workflow_id,
            name=name or "Workflow",
            description=description,
            tags=tags or [],
            is_archived=bool(is_archived),
        )


@pytest.mark.asyncio()
async def test_create_workflow_uses_authenticated_subject_and_workspace_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflows,
        "load_auth_settings",
        lambda: SimpleNamespace(enforce=True),
    )
    repository = _Repository()
    request = WorkflowCreateRequest(
        name="CLI uploaded workflow",
        tags=["langgraph", "cli-upload"],
        actor="cli",
    )
    policy = AuthorizationPolicy(
        RequestContext(
            subject="auth0|user-123",
            identity_type="user",
            scopes=frozenset({"workflows:write"}),
            workspace_ids=frozenset({"team-a"}),
        )
    )

    await workflows.create_workflow(request, repository, policy=policy)

    assert repository.last_actor == "auth0|user-123"
    assert repository.last_tags is not None
    assert "langgraph" in repository.last_tags
    assert "cli-upload" in repository.last_tags
    assert "workspace:team-a" in repository.last_tags


@pytest.mark.asyncio()
async def test_create_workflow_keeps_request_actor_when_context_unavailable() -> None:
    repository = _Repository()
    request = WorkflowCreateRequest(
        name="Legacy workflow",
        tags=["legacy"],
        actor="cli",
    )

    await workflows.create_workflow(request, repository)

    assert repository.last_actor == "cli"
    assert repository.last_tags == ["legacy"]


@pytest.mark.asyncio()
async def test_create_workflow_adds_workspace_tags_when_tags_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflows,
        "load_auth_settings",
        lambda: SimpleNamespace(enforce=True),
    )
    repository = _Repository()
    request = WorkflowCreateRequest(
        name="Tagless workflow",
        actor="cli",
    )
    policy = AuthorizationPolicy(
        RequestContext(
            subject="service-token-2",
            identity_type="service",
            scopes=frozenset({"workflows:write"}),
            workspace_ids=frozenset({"team-x"}),
        )
    )

    await workflows.create_workflow(request, repository, policy=policy)

    assert repository.last_actor == "service-token-2"
    assert repository.last_tags == ["workspace:team-x"]


@pytest.mark.asyncio()
async def test_create_workflow_normalizes_workspace_tag_casing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflows,
        "load_auth_settings",
        lambda: SimpleNamespace(enforce=True),
    )
    repository = _Repository()
    request = WorkflowCreateRequest(
        name="Case sensitive workspace",
        actor="cli",
    )
    policy = AuthorizationPolicy(
        RequestContext(
            subject="service-token-4",
            identity_type="service",
            scopes=frozenset({"workflows:write"}),
            workspace_ids=frozenset({"Team-X"}),
        )
    )

    await workflows.create_workflow(request, repository, policy=policy)

    assert repository.last_actor == "service-token-4"
    assert repository.last_tags == ["workspace:team-x"]


@pytest.mark.asyncio()
async def test_update_workflow_appends_workspace_tags_when_auth_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflows,
        "load_auth_settings",
        lambda: SimpleNamespace(enforce=True),
    )
    repository = _Repository()
    workflow = Workflow(name="Workflow")
    request = WorkflowUpdateRequest(tags=["cli-upload"], actor="cli")
    policy = AuthorizationPolicy(
        RequestContext(
            subject="service-token-1",
            identity_type="service",
            scopes=frozenset({"workflows:write"}),
            workspace_ids=frozenset({"ws-1", "ws-2"}),
        )
    )

    await workflows.update_workflow(workflow.id, request, repository, policy=policy)

    assert repository.last_actor == "service-token-1"
    assert repository.last_tags is not None
    assert "cli-upload" in repository.last_tags
    assert "workspace:ws-1" in repository.last_tags
    assert "workspace:ws-2" in repository.last_tags


def test_append_workspace_tags_returns_list_when_tags_none() -> None:
    """_append_workspace_tags returns workspace tag list when tags is None.

    Covers line 507.
    """
    context = RequestContext(
        subject="user-1",
        identity_type="user",
        scopes=frozenset({"workflows:write"}),
        workspace_ids=frozenset({"ws-a"}),
    )
    result = workflows._append_workspace_tags(None, context)
    assert result == ["workspace:ws-a"]


def test_append_workspace_tags_skips_duplicate_workspace_tag() -> None:
    """Workspace tag already present is not added again (branch 516->514)."""
    context = RequestContext(
        subject="user-1",
        identity_type="user",
        scopes=frozenset({"workflows:write"}),
        workspace_ids=frozenset({"ws-a"}),
    )
    result = workflows._append_workspace_tags(["workspace:ws-a"], context)
    assert result == ["workspace:ws-a"]


@pytest.mark.asyncio()
async def test_update_workflow_preserves_none_tags_when_request_omits_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflows,
        "load_auth_settings",
        lambda: SimpleNamespace(enforce=True),
    )
    repository = _Repository()
    workflow = Workflow(name="Workflow")
    request = WorkflowUpdateRequest(actor="cli")
    policy = AuthorizationPolicy(
        RequestContext(
            subject="service-token-3",
            identity_type="service",
            scopes=frozenset({"workflows:write"}),
            workspace_ids=frozenset({"ws-1"}),
        )
    )

    await workflows.update_workflow(workflow.id, request, repository, policy=policy)

    assert repository.last_actor == "service-token-3"
    assert repository.last_tags is None
