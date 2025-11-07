"""ServiceTokenManager integration flow tests."""

from __future__ import annotations
import hashlib
from datetime import UTC, datetime, timedelta
import pytest
from orcheo_backend.app.authentication import (
    AuthenticationError,
    ServiceTokenManager,
    ServiceTokenRecord,
)
from orcheo_backend.app.service_token_repository import (
    InMemoryServiceTokenRepository,
)


@pytest.mark.asyncio
async def test_service_token_manager_mint_rotate_revoke() -> None:
    """ServiceTokenManager should support rotation with overlap and revocation."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    secret, record = await manager.mint(
        scopes={"workflows:read"}, workspace_ids={"ws-1"}
    )

    assert record.matches(secret)
    all_tokens = await manager.all()
    assert record.identifier in {item.identifier for item in all_tokens}

    overlap_secret, rotated = await manager.rotate(
        record.identifier, overlap_seconds=60
    )
    authenticated = await manager.authenticate(secret)
    assert authenticated.identifier == record.identifier

    await manager.revoke(rotated.identifier, reason="test")
    with pytest.raises(AuthenticationError):
        await manager.authenticate(overlap_secret)


@pytest.mark.asyncio
async def test_service_token_manager_authenticate_revoked_token() -> None:
    """Authenticate raises when token is revoked."""

    token = "revoked-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()

    record = ServiceTokenRecord(
        identifier="revoked",
        secret_hash=digest,
        revoked_at=datetime.now(tz=UTC),
    )
    repository = InMemoryServiceTokenRepository()
    await repository.create(record)
    manager = ServiceTokenManager(repository)

    with pytest.raises(AuthenticationError) as exc:
        await manager.authenticate(token)
    assert exc.value.code == "auth.token_revoked"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_service_token_manager_authenticate_expired_token() -> None:
    """Authenticate raises when token is expired."""

    token = "expired-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()

    record = ServiceTokenRecord(
        identifier="expired",
        secret_hash=digest,
        expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
    )
    repository = InMemoryServiceTokenRepository()
    await repository.create(record)
    manager = ServiceTokenManager(repository)

    with pytest.raises(AuthenticationError) as exc:
        await manager.authenticate(token)
    assert exc.value.code == "auth.token_expired"
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_service_token_manager_mint_with_timedelta() -> None:
    """Mint can accept timedelta for expires_in."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    secret, record = await manager.mint(expires_in=timedelta(hours=1))

    assert record.matches(secret)
    assert record.expires_at is not None


@pytest.mark.asyncio
async def test_service_token_manager_mint_with_seconds() -> None:
    """Mint can accept int seconds for expires_in."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    secret, record = await manager.mint(expires_in=3600)

    assert record.matches(secret)
    assert record.expires_at is not None


@pytest.mark.asyncio
async def test_service_token_manager_mint_without_expiry() -> None:
    """Mint creates token without expiry when expires_in is None."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    secret, record = await manager.mint()

    assert record.matches(secret)
    assert record.expires_at is None


@pytest.mark.asyncio
async def test_service_token_manager_rotate_with_overlap() -> None:
    """Rotate allows overlap period before old token expires."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    original_secret, original_record = await manager.mint()

    new_secret, new_record = await manager.rotate(
        original_record.identifier,
        overlap_seconds=300,
    )

    # Both tokens should work during overlap
    authenticated_original = await manager.authenticate(original_secret)
    assert authenticated_original.identifier == original_record.identifier
    authenticated_new = await manager.authenticate(new_secret)
    assert authenticated_new.identifier == new_record.identifier


@pytest.mark.asyncio
async def test_service_token_manager_rotate_without_overlap() -> None:
    """Rotate with overlap_seconds=0 expires old token immediately."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)
    original_secret, original_record = await manager.mint()

    new_secret, new_record = await manager.rotate(
        original_record.identifier,
        overlap_seconds=0,
    )

    # New token should work
    authenticated = await manager.authenticate(new_secret)
    assert authenticated.identifier == new_record.identifier


@pytest.mark.asyncio
async def test_service_token_manager_rotate_nonexistent_raises() -> None:
    """Rotate raises KeyError for nonexistent identifier."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)

    with pytest.raises(KeyError):
        await manager.rotate("nonexistent")


@pytest.mark.asyncio
async def test_service_token_manager_revoke_nonexistent_raises() -> None:
    """Revoke raises KeyError for nonexistent identifier."""

    repository = InMemoryServiceTokenRepository()
    manager = ServiceTokenManager(repository)

    with pytest.raises(KeyError):
        await manager.revoke("nonexistent", reason="test")


@pytest.mark.asyncio
async def test_service_token_manager_all() -> None:
    """all() returns all managed tokens."""

    record1 = ServiceTokenRecord(identifier="token-1", secret_hash="hash1")
    record2 = ServiceTokenRecord(identifier="token-2", secret_hash="hash2")
    repository = InMemoryServiceTokenRepository()
    await repository.create(record1)
    await repository.create(record2)
    manager = ServiceTokenManager(repository)

    all_tokens = await manager.all()

    assert len(all_tokens) == 2
    identifiers = {token.identifier for token in all_tokens}
    assert "token-1" in identifiers
    assert "token-2" in identifiers
