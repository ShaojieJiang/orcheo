"""Tests for the list_service_tokens endpoint."""

from __future__ import annotations
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
import pytest
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthorizationError,
    AuthorizationPolicy,
    RequestContext,
    ServiceTokenRecord,
)
from orcheo_backend.app.service_token_endpoints import list_service_tokens


@pytest.mark.asyncio
async def test_list_service_tokens_success(admin_policy):
    """Endpoint should return all tokens without exposing secrets."""
    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_records = [
            ServiceTokenRecord(
                identifier="token-1",
                secret_hash="hash1",
                scopes=frozenset(["read"]),
                workspace_ids=frozenset(["ws-1"]),
                issued_at=datetime.now(tz=UTC),
            ),
            ServiceTokenRecord(
                identifier="token-2",
                secret_hash="hash2",
                scopes=frozenset(["write"]),
                workspace_ids=frozenset(["ws-2"]),
                issued_at=datetime.now(tz=UTC),
            ),
        ]
        mock_manager.all.return_value = mock_records
        mock_get_manager.return_value = mock_manager

        response = await list_service_tokens(admin_policy)

        assert response.total == 2
        assert len(response.tokens) == 2
        assert response.tokens[0].identifier == "token-1"
        assert response.tokens[1].identifier == "token-2"
        assert response.tokens[0].secret is None
        assert response.tokens[1].secret is None
        mock_manager.all.assert_called_once()


@pytest.mark.asyncio
async def test_list_service_tokens_empty(admin_policy):
    """Empty repositories should return zero results."""
    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.all.return_value = []
        mock_get_manager.return_value = mock_manager

        response = await list_service_tokens(admin_policy)

        assert response.total == 0
        assert len(response.tokens) == 0


@pytest.mark.asyncio
async def test_list_service_tokens_without_authentication():
    """Anonymous users cannot list tokens."""
    anonymous_context = RequestContext.anonymous()
    policy = AuthorizationPolicy(anonymous_context)

    with pytest.raises(AuthenticationError):
        await list_service_tokens(policy)


@pytest.mark.asyncio
async def test_list_service_tokens_without_required_scope():
    """Missing admin:tokens:read scope should raise AuthorizationError."""
    context = RequestContext(
        subject="user",
        identity_type="user",
        scopes=frozenset(["write"]),
    )
    policy = AuthorizationPolicy(context)

    with pytest.raises(AuthorizationError):
        await list_service_tokens(policy)
