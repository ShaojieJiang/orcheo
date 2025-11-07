"""Tests for the get_service_token endpoint."""

from __future__ import annotations
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException, status
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthorizationError,
    AuthorizationPolicy,
    RequestContext,
    ServiceTokenRecord,
)
from orcheo_backend.app.service_token_endpoints import get_service_token


@pytest.mark.asyncio
async def test_get_service_token_success(admin_policy):
    """Endpoint should return token metadata without secret."""
    mock_record = ServiceTokenRecord(
        identifier="token-123",
        secret_hash="hash123",
        scopes=frozenset(["read", "write"]),
        workspace_ids=frozenset(["ws-1"]),
        issued_at=datetime.now(tz=UTC),
    )

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager._repository.find_by_id.return_value = mock_record
        mock_get_manager.return_value = mock_manager

        response = await get_service_token("token-123", admin_policy)

        assert response.identifier == "token-123"
        assert response.scopes == ["read", "write"]
        assert response.workspace_ids == ["ws-1"]
        assert response.secret is None
        mock_manager._repository.find_by_id.assert_called_once_with("token-123")


@pytest.mark.asyncio
async def test_get_service_token_not_found(admin_policy):
    """Non-existent tokens should raise HTTP 404."""
    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager._repository.find_by_id.return_value = None
        mock_get_manager.return_value = mock_manager

        with pytest.raises(HTTPException) as exc_info:
            await get_service_token("nonexistent-token", admin_policy)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_get_service_token_without_authentication():
    """Anonymous users should be rejected."""
    anonymous_context = RequestContext.anonymous()
    policy = AuthorizationPolicy(anonymous_context)

    with pytest.raises(AuthenticationError):
        await get_service_token("token-123", policy)


@pytest.mark.asyncio
async def test_get_service_token_without_required_scope():
    """Missing admin:tokens:read scope should raise AuthorizationError."""
    context = RequestContext(
        subject="user",
        identity_type="user",
        scopes=frozenset(["write"]),
    )
    policy = AuthorizationPolicy(context)

    with pytest.raises(AuthorizationError):
        await get_service_token("token-123", policy)


@pytest.mark.asyncio
async def test_get_service_token_with_all_fields(admin_policy):
    """All record fields should be surfaced and sorted."""
    mock_record = ServiceTokenRecord(
        identifier="complete-token",
        secret_hash="hash",
        scopes=frozenset(["admin", "read", "write"]),
        workspace_ids=frozenset(["ws-1", "ws-2", "ws-3"]),
        issued_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
        expires_at=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        last_used_at=datetime(2025, 6, 15, 12, 30, 0, tzinfo=UTC),
        use_count=999,
        revoked_at=None,
        revocation_reason=None,
        rotated_to=None,
    )

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager._repository.find_by_id.return_value = mock_record
        mock_get_manager.return_value = mock_manager

        response = await get_service_token("complete-token", admin_policy)

        assert response.identifier == "complete-token"
        assert response.scopes == ["admin", "read", "write"]
        assert response.workspace_ids == ["ws-1", "ws-2", "ws-3"]
        assert response.use_count == 999
        assert response.last_used_at == datetime(2025, 6, 15, 12, 30, 0, tzinfo=UTC)
