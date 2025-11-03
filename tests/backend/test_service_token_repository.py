"""Unit tests for service token repository implementations."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import pytest
from orcheo_backend.app.authentication import ServiceTokenRecord
from orcheo_backend.app.service_token_repository import (
    InMemoryServiceTokenRepository,
    SqliteServiceTokenRepository,
)


@pytest.fixture
def sample_token_record() -> ServiceTokenRecord:
    """Create a sample service token record for testing."""
    return ServiceTokenRecord(
        identifier="test-token-123",
        secret_hash="abc123hash",
        scopes=frozenset(["read", "write"]),
        workspace_ids=frozenset(["ws-1", "ws-2"]),
        issued_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        expires_at=datetime(2025, 12, 31, 23, 59, 59, tzinfo=UTC),
    )


@pytest.fixture
def sample_token_with_rotation() -> ServiceTokenRecord:
    """Create a token with rotation details."""
    return ServiceTokenRecord(
        identifier="rotated-token",
        secret_hash="rotatedhash",
        scopes=frozenset(["admin"]),
        workspace_ids=frozenset(),
        issued_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
        rotation_expires_at=datetime(2025, 1, 1, 1, 0, 0, tzinfo=UTC),
        rotated_to="new-token-id",
    )


@pytest.fixture
def sample_revoked_token() -> ServiceTokenRecord:
    """Create a revoked token record."""
    return ServiceTokenRecord(
        identifier="revoked-token",
        secret_hash="revokedhash",
        scopes=frozenset(["read"]),
        workspace_ids=frozenset(["ws-1"]),
        issued_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
        revoked_at=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        revocation_reason="Security breach",
    )


class TestSqliteServiceTokenRepository:
    """Test cases for SQLite-backed service token repository."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        """Create a temporary database path."""
        return tmp_path / "test_tokens.db"

    @pytest.fixture
    def repository(self, db_path: Path) -> SqliteServiceTokenRepository:
        """Create a SQLite repository instance."""
        return SqliteServiceTokenRepository(db_path)

    @pytest.mark.asyncio
    async def test_list_all_empty(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """Test list_all returns empty list when no tokens exist."""
        tokens = await repository.list_all()
        assert tokens == []

    @pytest.mark.asyncio
    async def test_list_all_returns_all_tokens(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """Test list_all returns all tokens including revoked ones."""
        await repository.create(sample_token_record)
        await repository.create(sample_revoked_token)

        tokens = await repository.list_all()
        assert len(tokens) == 2
        identifiers = {token.identifier for token in tokens}
        assert "test-token-123" in identifiers
        assert "revoked-token" in identifiers

    @pytest.mark.asyncio
    async def test_list_active_excludes_revoked(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """Test list_active excludes revoked tokens."""
        await repository.create(sample_token_record)
        await repository.create(sample_revoked_token)

        active_tokens = await repository.list_active()
        assert len(active_tokens) == 1
        assert active_tokens[0].identifier == "test-token-123"

    @pytest.mark.asyncio
    async def test_list_active_excludes_expired(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """Test list_active excludes expired tokens."""
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

    @pytest.mark.asyncio
    async def test_list_active_includes_never_expiring(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """Test list_active includes tokens with no expiration."""
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

    @pytest.mark.asyncio
    async def test_find_by_id_found(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test find_by_id returns the correct token."""
        await repository.create(sample_token_record)

        found = await repository.find_by_id("test-token-123")
        assert found is not None
        assert found.identifier == "test-token-123"
        assert found.secret_hash == "abc123hash"
        assert found.scopes == frozenset(["read", "write"])
        assert found.workspace_ids == frozenset(["ws-1", "ws-2"])

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """Test find_by_id returns None for non-existent token."""
        found = await repository.find_by_id("nonexistent-id")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_hash_found(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test find_by_hash returns the correct token."""
        await repository.create(sample_token_record)

        found = await repository.find_by_hash("abc123hash")
        assert found is not None
        assert found.identifier == "test-token-123"
        assert found.secret_hash == "abc123hash"

    @pytest.mark.asyncio
    async def test_find_by_hash_not_found(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """Test find_by_hash returns None for non-existent hash."""
        found = await repository.find_by_hash("nonexistent-hash")
        assert found is None

    @pytest.mark.asyncio
    async def test_create_token_with_all_fields(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_with_rotation: ServiceTokenRecord,
    ) -> None:
        """Test create stores all token fields correctly."""
        created = await repository.create(sample_token_with_rotation)
        assert created.identifier == "rotated-token"

        found = await repository.find_by_id("rotated-token")
        assert found is not None
        assert found.secret_hash == "rotatedhash"
        assert found.scopes == frozenset(["admin"])
        assert found.rotation_expires_at == datetime(2025, 1, 1, 1, 0, 0, tzinfo=UTC)
        assert found.rotated_to == "new-token-id"

    @pytest.mark.asyncio
    async def test_create_token_with_empty_scopes_and_workspaces(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """Test create handles empty scopes and workspace_ids."""
        token = ServiceTokenRecord(
            identifier="minimal-token",
            secret_hash="minimalhash",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC),
        )

        await repository.create(token)
        found = await repository.find_by_id("minimal-token")
        assert found is not None
        assert found.scopes == frozenset()
        assert found.workspace_ids == frozenset()

    @pytest.mark.asyncio
    async def test_create_revoked_token(
        self,
        repository: SqliteServiceTokenRepository,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """Test create stores revocation information."""
        await repository.create(sample_revoked_token)

        found = await repository.find_by_id("revoked-token")
        assert found is not None
        assert found.revoked_at == datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert found.revocation_reason == "Security breach"

    @pytest.mark.asyncio
    async def test_update_token(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test update modifies token fields."""
        await repository.create(sample_token_record)

        # Update with new expiration and scopes
        updated_record = ServiceTokenRecord(
            identifier="test-token-123",
            secret_hash="newhash",
            scopes=frozenset(["admin", "delete"]),
            workspace_ids=frozenset(["ws-3"]),
            issued_at=sample_token_record.issued_at,
            expires_at=datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC),
        )

        await repository.update(updated_record)

        found = await repository.find_by_id("test-token-123")
        assert found is not None
        assert found.secret_hash == "newhash"
        assert found.scopes == frozenset(["admin", "delete"])
        assert found.workspace_ids == frozenset(["ws-3"])
        assert found.expires_at == datetime(2026, 6, 30, 23, 59, 59, tzinfo=UTC)

    @pytest.mark.asyncio
    async def test_update_token_revocation(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test update can revoke a token."""
        await repository.create(sample_token_record)

        revoked = ServiceTokenRecord(
            identifier="test-token-123",
            secret_hash=sample_token_record.secret_hash,
            scopes=sample_token_record.scopes,
            workspace_ids=sample_token_record.workspace_ids,
            issued_at=sample_token_record.issued_at,
            expires_at=sample_token_record.expires_at,
            revoked_at=datetime(2025, 2, 1, 0, 0, 0, tzinfo=UTC),
            revocation_reason="Testing revocation",
        )

        await repository.update(revoked)

        found = await repository.find_by_id("test-token-123")
        assert found is not None
        assert found.revoked_at == datetime(2025, 2, 1, 0, 0, 0, tzinfo=UTC)
        assert found.revocation_reason == "Testing revocation"

    @pytest.mark.asyncio
    async def test_update_token_rotation(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test update can set rotation fields."""
        await repository.create(sample_token_record)

        rotated = ServiceTokenRecord(
            identifier="test-token-123",
            secret_hash=sample_token_record.secret_hash,
            scopes=sample_token_record.scopes,
            workspace_ids=sample_token_record.workspace_ids,
            issued_at=sample_token_record.issued_at,
            expires_at=sample_token_record.expires_at,
            rotation_expires_at=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
            rotated_to="new-rotated-token",
        )

        await repository.update(rotated)

        found = await repository.find_by_id("test-token-123")
        assert found is not None
        assert found.rotation_expires_at == datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC)
        assert found.rotated_to == "new-rotated-token"

    @pytest.mark.asyncio
    async def test_delete_token(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test delete removes a token."""
        await repository.create(sample_token_record)

        found_before = await repository.find_by_id("test-token-123")
        assert found_before is not None

        await repository.delete("test-token-123")

        found_after = await repository.find_by_id("test-token-123")
        assert found_after is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_token(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """Test delete does not raise error for nonexistent token."""
        # Should not raise
        await repository.delete("nonexistent-token")

    @pytest.mark.asyncio
    async def test_record_usage_updates_last_used_and_count(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test record_usage updates last_used_at and use_count."""
        await repository.create(sample_token_record)

        initial = await repository.find_by_id("test-token-123")
        assert initial is not None
        assert initial.last_used_at is None
        assert initial.use_count == 0

        await repository.record_usage(
            "test-token-123",
            ip="192.168.1.1",
            user_agent="TestAgent/1.0",
        )

        after_use = await repository.find_by_id("test-token-123")
        assert after_use is not None
        assert after_use.last_used_at is not None
        assert after_use.use_count == 1

    @pytest.mark.asyncio
    async def test_record_usage_increments_count(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test record_usage increments use_count on multiple calls."""
        await repository.create(sample_token_record)

        await repository.record_usage("test-token-123")
        await repository.record_usage("test-token-123")
        await repository.record_usage("test-token-123")

        token = await repository.find_by_id("test-token-123")
        assert token is not None
        assert token.use_count == 3

    @pytest.mark.asyncio
    async def test_record_usage_without_ip_and_user_agent(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test record_usage works without ip and user_agent."""
        await repository.create(sample_token_record)

        await repository.record_usage("test-token-123")

        token = await repository.find_by_id("test-token-123")
        assert token is not None
        assert token.use_count == 1

    @pytest.mark.asyncio
    async def test_get_audit_log_returns_usage_entries(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test get_audit_log returns usage entries."""
        await repository.create(sample_token_record)

        await repository.record_usage(
            "test-token-123",
            ip="10.0.0.1",
            user_agent="Browser/1.0",
        )

        log = await repository.get_audit_log("test-token-123")
        assert len(log) == 1
        assert log[0]["token_id"] == "test-token-123"
        assert log[0]["action"] == "used"
        assert log[0]["ip_address"] == "10.0.0.1"
        assert log[0]["user_agent"] == "Browser/1.0"

    @pytest.mark.asyncio
    async def test_get_audit_log_respects_limit(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test get_audit_log respects the limit parameter."""
        await repository.create(sample_token_record)

        # Create 10 usage entries
        for _ in range(10):
            await repository.record_usage("test-token-123")

        log = await repository.get_audit_log("test-token-123", limit=5)
        assert len(log) == 5

    @pytest.mark.asyncio
    async def test_get_audit_log_empty_for_nonexistent_token(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """Test get_audit_log returns empty list for nonexistent token."""
        log = await repository.get_audit_log("nonexistent-token")
        assert log == []

    @pytest.mark.asyncio
    async def test_record_audit_event(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test record_audit_event creates audit log entries."""
        await repository.create(sample_token_record)

        await repository.record_audit_event(
            "test-token-123",
            "created",
            actor="admin",
            ip="127.0.0.1",
            details={"reason": "Testing"},
        )

        log = await repository.get_audit_log("test-token-123")
        assert len(log) == 1
        assert log[0]["action"] == "created"
        assert log[0]["actor"] == "admin"
        assert log[0]["ip_address"] == "127.0.0.1"

    @pytest.mark.asyncio
    async def test_record_audit_event_without_optional_fields(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test record_audit_event works without optional fields."""
        await repository.create(sample_token_record)

        await repository.record_audit_event(
            "test-token-123",
            "rotated",
        )

        log = await repository.get_audit_log("test-token-123")
        assert len(log) == 1
        assert log[0]["action"] == "rotated"
        assert log[0]["actor"] is None
        assert log[0]["ip_address"] is None

    @pytest.mark.asyncio
    async def test_database_path_creation(self, tmp_path: Path) -> None:
        """Test that repository creates parent directories."""
        nested_path = tmp_path / "nested" / "dirs" / "tokens.db"
        repository = SqliteServiceTokenRepository(nested_path)

        # Should not raise and parent dirs should exist
        assert nested_path.parent.exists()

        # Verify we can create tokens
        token = ServiceTokenRecord(
            identifier="test-nested",
            secret_hash="hash",
            scopes=frozenset(),
            workspace_ids=frozenset(),
            issued_at=datetime.now(tz=UTC),
        )
        await repository.create(token)
        found = await repository.find_by_id("test-nested")
        assert found is not None


class TestInMemoryServiceTokenRepository:
    """Test cases for in-memory service token repository."""

    @pytest.fixture
    def repository(self) -> InMemoryServiceTokenRepository:
        """Create an in-memory repository instance."""
        return InMemoryServiceTokenRepository()

    @pytest.mark.asyncio
    async def test_list_all_empty(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """Test list_all returns empty list when no tokens exist."""
        tokens = await repository.list_all()
        assert tokens == []

    @pytest.mark.asyncio
    async def test_list_all_returns_all_tokens(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """Test list_all returns all tokens."""
        await repository.create(sample_token_record)
        await repository.create(sample_revoked_token)

        tokens = await repository.list_all()
        assert len(tokens) == 2

    @pytest.mark.asyncio
    async def test_list_active_filters_revoked_and_expired(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """Test list_active filters out revoked and expired tokens."""
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

    @pytest.mark.asyncio
    async def test_find_by_id(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test find_by_id returns correct token."""
        await repository.create(sample_token_record)

        found = await repository.find_by_id("test-token-123")
        assert found is not None
        assert found.identifier == "test-token-123"

    @pytest.mark.asyncio
    async def test_find_by_id_not_found(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """Test find_by_id returns None for nonexistent token."""
        found = await repository.find_by_id("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_hash(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test find_by_hash returns correct token."""
        await repository.create(sample_token_record)

        found = await repository.find_by_hash("abc123hash")
        assert found is not None
        assert found.identifier == "test-token-123"

    @pytest.mark.asyncio
    async def test_find_by_hash_not_found(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """Test find_by_hash returns None for nonexistent hash."""
        found = await repository.find_by_hash("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_by_hash_with_multiple_tokens(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """Test find_by_hash searches through multiple tokens."""
        # Create multiple tokens to ensure loop iteration
        await repository.create(sample_token_record)
        await repository.create(sample_revoked_token)

        # Find the second token by hash
        found = await repository.find_by_hash("revokedhash")
        assert found is not None
        assert found.identifier == "revoked-token"

        # Verify first token can still be found
        found_first = await repository.find_by_hash("abc123hash")
        assert found_first is not None
        assert found_first.identifier == "test-token-123"

    @pytest.mark.asyncio
    async def test_create_and_update(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test create and update operations."""
        created = await repository.create(sample_token_record)
        assert created.identifier == "test-token-123"

        # Update with new scopes
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

    @pytest.mark.asyncio
    async def test_delete(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test delete removes token."""
        await repository.create(sample_token_record)

        found_before = await repository.find_by_id("test-token-123")
        assert found_before is not None

        await repository.delete("test-token-123")

        found_after = await repository.find_by_id("test-token-123")
        assert found_after is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """Test delete handles nonexistent token gracefully."""
        # Should not raise
        await repository.delete("nonexistent")

    @pytest.mark.asyncio
    async def test_record_usage(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test record_usage updates token and creates audit log."""
        await repository.create(sample_token_record)

        await repository.record_usage(
            "test-token-123",
            ip="10.0.0.1",
            user_agent="TestAgent/1.0",
        )

        token = await repository.find_by_id("test-token-123")
        assert token is not None
        assert token.use_count == 1
        assert token.last_used_at is not None

        log = await repository.get_audit_log("test-token-123")
        assert len(log) == 1
        assert log[0]["action"] == "used"
        assert log[0]["ip_address"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_record_usage_for_nonexistent_token(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """Test record_usage handles nonexistent token gracefully."""
        # Should not raise but should create audit log entry
        await repository.record_usage("nonexistent-token")

        log = await repository.get_audit_log("nonexistent-token")
        assert len(log) == 1

    @pytest.mark.asyncio
    async def test_get_audit_log_limit(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test get_audit_log respects limit parameter."""
        await repository.create(sample_token_record)

        # Create multiple usage entries
        for _ in range(10):
            await repository.record_usage("test-token-123")

        log = await repository.get_audit_log("test-token-123", limit=5)
        # In-memory implementation returns last N entries
        assert len(log) == 5

    @pytest.mark.asyncio
    async def test_record_audit_event(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """Test record_audit_event creates audit entries."""
        await repository.create(sample_token_record)

        await repository.record_audit_event(
            "test-token-123",
            "revoked",
            actor="admin",
            ip="127.0.0.1",
            details={"reason": "Test"},
        )

        log = await repository.get_audit_log("test-token-123")
        assert len(log) == 1
        assert log[0]["action"] == "revoked"
        assert log[0]["actor"] == "admin"
