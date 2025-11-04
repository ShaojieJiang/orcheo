"""Tests for service token management endpoints."""

from __future__ import annotations
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import HTTPException, status
from orcheo_backend.app.authentication import (
    AuthenticationError,
    AuthorizationError,
    AuthorizationPolicy,
    RequestContext,
    ServiceTokenManager,
    ServiceTokenRecord,
)
from orcheo_backend.app.service_token_endpoints import (
    CreateServiceTokenRequest,
    RevokeServiceTokenRequest,
    RotateServiceTokenRequest,
    _record_to_response,
    create_service_token,
    get_service_token,
    list_service_tokens,
    revoke_service_token,
    rotate_service_token,
)
from orcheo_backend.app.service_token_repository import (
    InMemoryServiceTokenRepository,
)


@pytest.fixture
def mock_repository():
    """Create an in-memory repository for testing."""
    return InMemoryServiceTokenRepository()


@pytest.fixture
async def mock_token_manager(mock_repository):
    """Create a token manager with in-memory repository."""
    return ServiceTokenManager(mock_repository)


@pytest.fixture
def authenticated_context():
    """Create an authenticated context with required scopes."""
    return RequestContext(
        subject="admin-user",
        identity_type="user",
        scopes=frozenset(["admin:tokens:read", "admin:tokens:write"]),
    )


@pytest.fixture
def admin_policy(authenticated_context):
    """Create an authorization policy with admin scopes."""
    return AuthorizationPolicy(authenticated_context)


def test_record_to_response():
    """Test _record_to_response converts ServiceTokenRecord to API response."""
    record = ServiceTokenRecord(
        identifier="test-token",
        secret_hash="hash123",
        scopes=frozenset(["read", "write"]),
        workspace_ids=frozenset(["ws-1", "ws-2"]),
        issued_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        expires_at=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
        last_used_at=datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC),
        use_count=42,
        revoked_at=None,
        revocation_reason=None,
        rotated_to=None,
    )

    response = _record_to_response(
        record,
        secret="secret-value",
        message="Test message",
    )

    assert response.identifier == "test-token"
    assert response.secret == "secret-value"
    assert response.scopes == ["read", "write"]
    assert response.workspace_ids == ["ws-1", "ws-2"]
    assert response.issued_at == datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert response.expires_at == datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC)
    assert response.last_used_at == datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)
    assert response.use_count == 42
    assert response.revoked_at is None
    assert response.revocation_reason is None
    assert response.rotated_to is None
    assert response.message == "Test message"


def test_record_to_response_with_revocation():
    """Test _record_to_response includes revocation details."""
    revoked_at = datetime(2025, 2, 1, 10, 0, 0, tzinfo=UTC)
    record = ServiceTokenRecord(
        identifier="revoked-token",
        secret_hash="hash456",
        scopes=frozenset(),
        workspace_ids=frozenset(),
        issued_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        revoked_at=revoked_at,
        revocation_reason="Security breach",
        rotated_to="new-token-id",
    )

    response = _record_to_response(record)

    assert response.identifier == "revoked-token"
    assert response.secret is None
    assert response.revoked_at == revoked_at
    assert response.revocation_reason == "Security breach"
    assert response.rotated_to == "new-token-id"


@pytest.mark.asyncio
async def test_create_service_token_success(admin_policy):
    """Test create_service_token endpoint creates a new token."""
    request = CreateServiceTokenRequest(
        identifier="my-token",
        scopes=["read", "write"],
        workspace_ids=["ws-1"],
        expires_in_seconds=3600,
    )

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_secret = "secret-token-value"
        mock_record = ServiceTokenRecord(
            identifier="my-token",
            secret_hash="hash123",
            scopes=frozenset(["read", "write"]),
            workspace_ids=frozenset(["ws-1"]),
            issued_at=datetime.now(tz=UTC),
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )
        mock_manager.mint.return_value = (mock_secret, mock_record)
        mock_get_manager.return_value = mock_manager

        response = await create_service_token(request, admin_policy)

        assert response.identifier == "my-token"
        assert response.secret == mock_secret
        assert "Store this token securely" in response.message
        mock_manager.mint.assert_called_once_with(
            identifier="my-token",
            scopes=["read", "write"],
            workspace_ids=["ws-1"],
            expires_in=3600,
        )


@pytest.mark.asyncio
async def test_create_service_token_without_authentication():
    """Test create_service_token requires authentication."""
    anonymous_context = RequestContext.anonymous()
    policy = AuthorizationPolicy(anonymous_context)
    request = CreateServiceTokenRequest()

    with pytest.raises(AuthenticationError):
        await create_service_token(request, policy)


@pytest.mark.asyncio
async def test_create_service_token_without_required_scope():
    """Test create_service_token requires admin:tokens:write scope."""
    context = RequestContext(
        subject="user",
        identity_type="user",
        scopes=frozenset(["read"]),
    )
    policy = AuthorizationPolicy(context)
    request = CreateServiceTokenRequest()

    with pytest.raises(AuthorizationError):
        await create_service_token(request, policy)


@pytest.mark.asyncio
async def test_list_service_tokens_success(admin_policy):
    """Test list_service_tokens endpoint returns all tokens."""
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
        # Secrets should not be included
        assert response.tokens[0].secret is None
        assert response.tokens[1].secret is None
        mock_manager.all.assert_called_once()


@pytest.mark.asyncio
async def test_list_service_tokens_empty(admin_policy):
    """Test list_service_tokens returns empty list when no tokens exist."""
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
    """Test list_service_tokens requires authentication."""
    anonymous_context = RequestContext.anonymous()
    policy = AuthorizationPolicy(anonymous_context)

    with pytest.raises(AuthenticationError):
        await list_service_tokens(policy)


@pytest.mark.asyncio
async def test_list_service_tokens_without_required_scope():
    """Test list_service_tokens requires admin:tokens:read scope."""
    context = RequestContext(
        subject="user",
        identity_type="user",
        scopes=frozenset(["write"]),
    )
    policy = AuthorizationPolicy(context)

    with pytest.raises(AuthorizationError):
        await list_service_tokens(policy)


@pytest.mark.asyncio
async def test_get_service_token_success(admin_policy):
    """Test get_service_token endpoint retrieves a specific token."""
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
        # Secret should not be included
        assert response.secret is None
        mock_manager._repository.find_by_id.assert_called_once_with("token-123")


@pytest.mark.asyncio
async def test_get_service_token_not_found(admin_policy):
    """Test get_service_token raises 404 when token doesn't exist."""
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
    """Test get_service_token requires authentication."""
    anonymous_context = RequestContext.anonymous()
    policy = AuthorizationPolicy(anonymous_context)

    with pytest.raises(AuthenticationError):
        await get_service_token("token-123", policy)


@pytest.mark.asyncio
async def test_get_service_token_without_required_scope():
    """Test get_service_token requires admin:tokens:read scope."""
    context = RequestContext(
        subject="user",
        identity_type="user",
        scopes=frozenset(["write"]),
    )
    policy = AuthorizationPolicy(context)

    with pytest.raises(AuthorizationError):
        await get_service_token("token-123", policy)


@pytest.mark.asyncio
async def test_rotate_service_token_success(admin_policy):
    """Test rotate_service_token endpoint rotates a token."""
    request = RotateServiceTokenRequest(
        overlap_seconds=300,
        expires_in_seconds=7200,
    )

    mock_new_secret = "new-secret-value"
    mock_new_record = ServiceTokenRecord(
        identifier="new-token-id",
        secret_hash="new-hash",
        scopes=frozenset(["read"]),
        workspace_ids=frozenset(["ws-1"]),
        issued_at=datetime.now(tz=UTC),
        expires_at=datetime.now(tz=UTC) + timedelta(hours=2),
    )

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.rotate.return_value = (mock_new_secret, mock_new_record)
        mock_get_manager.return_value = mock_manager

        response = await rotate_service_token("old-token-id", request, admin_policy)

        assert response.identifier == "new-token-id"
        assert response.secret == mock_new_secret
        assert "Old token 'old-token-id' valid for 300s" in response.message
        mock_manager.rotate.assert_called_once_with(
            "old-token-id",
            overlap_seconds=300,
            expires_in=7200,
        )


@pytest.mark.asyncio
async def test_rotate_service_token_not_found(admin_policy):
    """Test rotate_service_token raises 404 when token doesn't exist."""
    request = RotateServiceTokenRequest(overlap_seconds=300)

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.rotate.side_effect = KeyError("Token not found")
        mock_get_manager.return_value = mock_manager

        with pytest.raises(HTTPException) as exc_info:
            await rotate_service_token("nonexistent-token", request, admin_policy)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_rotate_service_token_without_authentication():
    """Test rotate_service_token requires authentication."""
    anonymous_context = RequestContext.anonymous()
    policy = AuthorizationPolicy(anonymous_context)
    request = RotateServiceTokenRequest()

    with pytest.raises(AuthenticationError):
        await rotate_service_token("token-123", request, policy)


@pytest.mark.asyncio
async def test_rotate_service_token_without_required_scope():
    """Test rotate_service_token requires admin:tokens:write scope."""
    context = RequestContext(
        subject="user",
        identity_type="user",
        scopes=frozenset(["read"]),
    )
    policy = AuthorizationPolicy(context)
    request = RotateServiceTokenRequest()

    with pytest.raises(AuthorizationError):
        await rotate_service_token("token-123", request, policy)


@pytest.mark.asyncio
async def test_revoke_service_token_success(admin_policy):
    """Test revoke_service_token endpoint revokes a token."""
    request = RevokeServiceTokenRequest(reason="Security breach detected")

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.revoke.return_value = None
        mock_get_manager.return_value = mock_manager

        response = await revoke_service_token("token-to-revoke", request, admin_policy)

        # Should return None (204 No Content)
        assert response is None
        mock_manager.revoke.assert_called_once_with(
            "token-to-revoke",
            reason="Security breach detected",
        )


@pytest.mark.asyncio
async def test_revoke_service_token_not_found(admin_policy):
    """Test revoke_service_token raises 404 when token doesn't exist."""
    request = RevokeServiceTokenRequest(reason="Test")

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.revoke.side_effect = KeyError("Token not found")
        mock_get_manager.return_value = mock_manager

        with pytest.raises(HTTPException) as exc_info:
            await revoke_service_token("nonexistent-token", request, admin_policy)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_revoke_service_token_without_authentication():
    """Test revoke_service_token requires authentication."""
    anonymous_context = RequestContext.anonymous()
    policy = AuthorizationPolicy(anonymous_context)
    request = RevokeServiceTokenRequest(reason="Test")

    with pytest.raises(AuthenticationError):
        await revoke_service_token("token-123", request, policy)


@pytest.mark.asyncio
async def test_revoke_service_token_without_required_scope():
    """Test revoke_service_token requires admin:tokens:write scope."""
    context = RequestContext(
        subject="user",
        identity_type="user",
        scopes=frozenset(["read"]),
    )
    policy = AuthorizationPolicy(context)
    request = RevokeServiceTokenRequest(reason="Test")

    with pytest.raises(AuthorizationError):
        await revoke_service_token("token-123", request, policy)


@pytest.mark.asyncio
async def test_create_service_token_with_default_values(admin_policy):
    """Test create_service_token with minimal request (default values)."""
    request = CreateServiceTokenRequest()

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_secret = "generated-secret"
        mock_record = ServiceTokenRecord(
            identifier="auto-generated-id",
            secret_hash="hash",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime.now(tz=UTC),
        )
        mock_manager.mint.return_value = (mock_secret, mock_record)
        mock_get_manager.return_value = mock_manager

        response = await create_service_token(request, admin_policy)

        assert response.identifier == "auto-generated-id"
        assert response.secret == mock_secret
        mock_manager.mint.assert_called_once_with(
            identifier=None,
            scopes=[],
            workspace_ids=[],
            expires_in=None,
        )


@pytest.mark.asyncio
async def test_rotate_service_token_with_default_overlap(admin_policy):
    """Test rotate_service_token uses default overlap of 300 seconds."""
    request = RotateServiceTokenRequest()  # Uses default overlap_seconds=300

    mock_new_secret = "new-secret"
    mock_new_record = ServiceTokenRecord(
        identifier="new-token",
        secret_hash="hash",
        scopes=frozenset(),
        workspace_ids=frozenset(),
        issued_at=datetime.now(tz=UTC),
    )

    with patch(
        "orcheo_backend.app.service_token_endpoints.get_service_token_manager"
    ) as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.rotate.return_value = (mock_new_secret, mock_new_record)
        mock_get_manager.return_value = mock_manager

        response = await rotate_service_token("old-token", request, admin_policy)

        # Verify default overlap of 300 is used
        mock_manager.rotate.assert_called_once_with(
            "old-token",
            overlap_seconds=300,
            expires_in=None,
        )
        assert "300s" in response.message


@pytest.mark.asyncio
async def test_get_service_token_with_all_fields(admin_policy):
    """Test get_service_token returns all fields from record."""
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
        # Scopes should be sorted
        assert response.scopes == ["admin", "read", "write"]
        # Workspace IDs should be sorted
        assert response.workspace_ids == ["ws-1", "ws-2", "ws-3"]
        assert response.use_count == 999
        assert response.last_used_at == datetime(2025, 6, 15, 12, 30, 0, tzinfo=UTC)
