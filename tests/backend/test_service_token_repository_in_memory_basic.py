"""Basic CRUD and lookup tests for the in-memory service token repository."""

from __future__ import annotations
from datetime import UTC, datetime
import pytest
from orcheo_backend.app.authentication import ServiceTokenRecord
from orcheo_backend.app.service_token_repository import InMemoryServiceTokenRepository


pytestmark = pytest.mark.asyncio


class TestInMemoryServiceTokenRepositoryBasic:
    """List, lookup, and mutation tests for the in-memory repository."""

    @pytest.fixture
    def repository(self) -> InMemoryServiceTokenRepository:
        """Create an in-memory repository instance."""
        return InMemoryServiceTokenRepository()

    async def test_list_all_empty(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """list_all returns empty list when no tokens exist."""
        tokens = await repository.list_all()
        assert tokens == []

    async def test_list_all_returns_all_tokens(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """list_all returns all tokens."""
        await repository.create(sample_token_record)
        await repository.create(sample_revoked_token)

        tokens = await repository.list_all()
        assert len(tokens) == 2

    async def test_list_active_filters_revoked_and_expired(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """list_active filters out revoked and expired tokens."""
        active = ServiceTokenRecord(
            identifier="active",
            secret_hash="hash1",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
            expires_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        )
        expired = ServiceTokenRecord(
            identifier="expired",
            secret_hash="hash2",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC),
            expires_at=datetime(2024, 12, 31, 0, 0, 0, tzinfo=UTC),
        )
        revoked = ServiceTokenRecord(
            identifier="revoked",
            secret_hash="hash3",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
            revoked_at=datetime(2025, 1, 15, 0, 0, 0, tzinfo=UTC),
        )

        await repository.create(active)
        await repository.create(expired)
        await repository.create(revoked)

        now = datetime(2025, 6, 1, 0, 0, 0, tzinfo=UTC)
        active_tokens = await repository.list_active(now=now)
        assert len(active_tokens) == 1
        assert active_tokens[0].identifier == "active"

    async def test_find_by_id(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """find_by_id returns correct token."""
        await repository.create(sample_token_record)

        found = await repository.find_by_id("test-token-123")
        assert found is not None
        assert found.identifier == "test-token-123"

    async def test_find_by_id_not_found(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """find_by_id returns None for nonexistent token."""
        found = await repository.find_by_id("nonexistent")
        assert found is None

    async def test_find_by_hash(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """find_by_hash returns correct token."""
        await repository.create(sample_token_record)

        found = await repository.find_by_hash("abc123hash")
        assert found is not None
        assert found.identifier == "test-token-123"

    async def test_find_by_hash_not_found(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """find_by_hash returns None for nonexistent hash."""
        found = await repository.find_by_hash("nonexistent")
        assert found is None

    async def test_find_by_hash_with_multiple_tokens(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """find_by_hash searches through multiple tokens."""
        await repository.create(sample_token_record)
        await repository.create(sample_revoked_token)

        found = await repository.find_by_hash("revokedhash")
        assert found is not None
        assert found.identifier == "revoked-token"

        found_first = await repository.find_by_hash("abc123hash")
        assert found_first is not None
        assert found_first.identifier == "test-token-123"

    async def test_create_and_update(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """create and update operations."""
        created = await repository.create(sample_token_record)
        assert created.identifier == "test-token-123"

        updated_record = ServiceTokenRecord(
            identifier="test-token-123",
            secret_hash="newhash",
            scopes=frozenset(["admin"]),
            workspace_ids=sample_token_record.workspace_ids,
            issued_at=sample_token_record.issued_at,
        )

        await repository.update(updated_record)
        found = await repository.find_by_id("test-token-123")
        assert found is not None
        assert found.secret_hash == "newhash"
        assert found.scopes == frozenset(["admin"])

    async def test_delete(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """delete removes token."""
        await repository.create(sample_token_record)

        found_before = await repository.find_by_id("test-token-123")
        assert found_before is not None

        await repository.delete("test-token-123")

        found_after = await repository.find_by_id("test-token-123")
        assert found_after is None

    async def test_delete_nonexistent(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """delete handles nonexistent token gracefully."""
        await repository.delete("nonexistent")
