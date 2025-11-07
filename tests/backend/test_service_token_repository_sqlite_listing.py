"""Tests for listing and lookup behavior of the SQLite service token repository."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import pytest
from orcheo_backend.app.authentication import ServiceTokenRecord
from orcheo_backend.app.service_token_repository import SqliteServiceTokenRepository


pytestmark = pytest.mark.asyncio


class TestSqliteServiceTokenRepositoryListing:
    """List and retrieval focused tests for the SQLite repository."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        """Create a temporary database path."""
        return tmp_path / "test_tokens.db"

    @pytest.fixture
    def repository(self, db_path: Path) -> SqliteServiceTokenRepository:
        """Create a SQLite repository instance."""
        return SqliteServiceTokenRepository(db_path)

    async def test_list_all_empty(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """list_all returns empty list when no tokens exist."""
        tokens = await repository.list_all()
        assert tokens == []

    async def test_list_all_returns_all_tokens(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """list_all returns all tokens including revoked ones."""
        await repository.create(sample_token_record)
        await repository.create(sample_revoked_token)

        tokens = await repository.list_all()
        assert len(tokens) == 2
        identifiers = {token.identifier for token in tokens}
        assert "test-token-123" in identifiers
        assert "revoked-token" in identifiers

    async def test_list_active_excludes_revoked(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """list_active excludes revoked tokens."""
        await repository.create(sample_token_record)
        await repository.create(sample_revoked_token)

        active_tokens = await repository.list_active()
        assert len(active_tokens) == 1
        assert active_tokens[0].identifier == "test-token-123"

    async def test_list_active_excludes_expired(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """list_active excludes expired tokens."""
        expired_token = ServiceTokenRecord(
            identifier="expired-token",
            secret_hash="expiredhash",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            expires_at=datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC),
        )
        active_token = ServiceTokenRecord(
            identifier="active-token",
            secret_hash="activehash",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )

        await repository.create(expired_token)
        await repository.create(active_token)

        now = datetime(2025, 6, 1, 0, 0, 0, tzinfo=UTC)
        active_tokens = await repository.list_active(now=now)
        assert len(active_tokens) == 1
        assert active_tokens[0].identifier == "active-token"

    async def test_list_active_includes_never_expiring(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """list_active includes tokens with no expiration."""
        never_expires = ServiceTokenRecord(
            identifier="forever-token",
            secret_hash="foreverhash",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
            expires_at=None,
        )

        await repository.create(never_expires)

        active_tokens = await repository.list_active()
        assert len(active_tokens) == 1
        assert active_tokens[0].identifier == "forever-token"

    async def test_find_by_id_found(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """find_by_id returns the correct token."""
        await repository.create(sample_token_record)

        found = await repository.find_by_id("test-token-123")
        assert found is not None
        assert found.identifier == "test-token-123"
        assert found.secret_hash == "abc123hash"
        assert found.scopes == frozenset(["read", "write"])
        assert found.workspace_ids == frozenset(["ws-1", "ws-2"])

    async def test_find_by_id_not_found(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """find_by_id returns None for non-existent token."""
        found = await repository.find_by_id("nonexistent-id")
        assert found is None

    async def test_find_by_hash_found(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """find_by_hash returns the correct token."""
        await repository.create(sample_token_record)

        found = await repository.find_by_hash("abc123hash")
        assert found is not None
        assert found.identifier == "test-token-123"
        assert found.secret_hash == "abc123hash"

    async def test_find_by_hash_not_found(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """find_by_hash returns None for non-existent hash."""
        found = await repository.find_by_hash("nonexistent-hash")
        assert found is None
