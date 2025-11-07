"""Tests covering create, update, and delete behavior of the SQLite repository."""

from __future__ import annotations
from datetime import UTC, datetime
from pathlib import Path
import pytest
from orcheo_backend.app.authentication import ServiceTokenRecord
from orcheo_backend.app.service_token_repository import SqliteServiceTokenRepository


pytestmark = pytest.mark.asyncio


class TestSqliteServiceTokenRepositoryMutations:
    """Mutation focused tests for the SQLite repository."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        """Create a temporary database path."""
        return tmp_path / "test_tokens.db"

    @pytest.fixture
    def repository(self, db_path: Path) -> SqliteServiceTokenRepository:
        """Create a SQLite repository instance."""
        return SqliteServiceTokenRepository(db_path)

    async def test_create_token_with_all_fields(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_with_rotation: ServiceTokenRecord,
    ) -> None:
        """create stores all token fields correctly."""
        created = await repository.create(sample_token_with_rotation)
        assert created.identifier == "rotated-token"

        found = await repository.find_by_id("rotated-token")
        assert found is not None
        assert found.secret_hash == "rotatedhash"
        assert found.scopes == frozenset(["admin"])
        assert found.rotation_expires_at == datetime(2025, 1, 1, 1, 0, 0, tzinfo=UTC)
        assert found.rotated_to == "new-token-id"

    async def test_create_token_with_empty_scopes_and_workspaces(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """create handles empty scopes and workspace_ids."""
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

    async def test_create_revoked_token(
        self,
        repository: SqliteServiceTokenRepository,
        sample_revoked_token: ServiceTokenRecord,
    ) -> None:
        """create stores revocation information."""
        await repository.create(sample_revoked_token)

        found = await repository.find_by_id("revoked-token")
        assert found is not None
        assert found.revoked_at == datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        assert found.revocation_reason == "Security breach"

    async def test_update_token(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """update modifies token fields."""
        await repository.create(sample_token_record)

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

    async def test_update_token_revocation(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """update can revoke a token."""
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

    async def test_update_token_rotation(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """update can set rotation fields."""
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

    async def test_delete_token(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """delete removes a token."""
        await repository.create(sample_token_record)

        found_before = await repository.find_by_id("test-token-123")
        assert found_before is not None

        await repository.delete("test-token-123")

        found_after = await repository.find_by_id("test-token-123")
        assert found_after is None

    async def test_delete_nonexistent_token(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """delete does not raise error for nonexistent token."""
        await repository.delete("nonexistent-token")

    async def test_database_path_creation(self, tmp_path: Path) -> None:
        """Repository should create parent directories for the database file."""
        nested_path = tmp_path / "nested" / "dirs" / "tokens.db"
        repository = SqliteServiceTokenRepository(nested_path)

        assert nested_path.parent.exists()

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
