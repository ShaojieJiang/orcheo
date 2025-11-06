"""Utility-level ChatKit tests covering workspace resolution and websocket auth."""

from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
from orcheo_backend.app import (
    _resolve_chatkit_workspace_id,
    workflow_websocket,
)
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthorizationPolicy,
    RequestContext,
)
from orcheo_backend.app.schemas import ChatKitSessionRequest


@pytest.mark.asyncio()
async def test_workflow_websocket_authentication_error() -> None:
    """Websocket handler should return early on authentication errors."""

    mock_websocket = MagicMock()

    with patch(
        "orcheo_backend.app.authenticate_websocket",
        side_effect=AuthenticationError("Unauthorized"),
    ):
        await workflow_websocket(mock_websocket, "test-workflow-id")

    mock_websocket.accept.assert_not_called()


@pytest.mark.asyncio()
async def test_resolve_chatkit_workspace_id_from_metadata_keys() -> None:
    """Resolve workspace ID from various metadata keys."""

    policy = AuthorizationPolicy(
        RequestContext(
            subject="test",
            identity_type="user",
            scopes=frozenset(),
            workspace_ids=frozenset(),
        )
    )

    request = ChatKitSessionRequest(
        workflow_id=None,
        metadata={"workspace_id": "ws-from-metadata"},
    )
    assert _resolve_chatkit_workspace_id(policy, request) == "ws-from-metadata"

    request = ChatKitSessionRequest(
        workflow_id=None,
        metadata={"workspaceId": "ws-camelcase"},
    )
    assert _resolve_chatkit_workspace_id(policy, request) == "ws-camelcase"

    request = ChatKitSessionRequest(
        workflow_id=None,
        metadata={"workspace": "ws-short"},
    )
    assert _resolve_chatkit_workspace_id(policy, request) == "ws-short"


@pytest.mark.asyncio()
async def test_resolve_chatkit_workspace_id_from_policy() -> None:
    """Resolve workspace ID from policy when exactly one workspace."""

    single_policy = AuthorizationPolicy(
        RequestContext(
            subject="test",
            identity_type="user",
            scopes=frozenset(),
            workspace_ids=frozenset({"ws-single"}),
        )
    )

    request = ChatKitSessionRequest(workflow_id=None, metadata={})
    assert _resolve_chatkit_workspace_id(single_policy, request) == "ws-single"

    multi_policy = AuthorizationPolicy(
        RequestContext(
            subject="test",
            identity_type="user",
            scopes=frozenset(),
            workspace_ids=frozenset({"ws-1", "ws-2"}),
        )
    )

    assert _resolve_chatkit_workspace_id(multi_policy, request) is None
