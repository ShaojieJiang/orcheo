"""Tests covering usage tracking and audit logging for the SQLite repository."""

from __future__ import annotations
from pathlib import Path
import pytest
from orcheo_backend.app.authentication import ServiceTokenRecord
from orcheo_backend.app.service_token_repository import SqliteServiceTokenRepository


pytestmark = pytest.mark.asyncio


class TestSqliteServiceTokenRepositoryAudit:
    """Usage and audit specific tests for the SQLite repository."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        """Create a temporary database path."""
        return tmp_path / "test_tokens.db"

    @pytest.fixture
    def repository(self, db_path: Path) -> SqliteServiceTokenRepository:
        """Create a SQLite repository instance."""
        return SqliteServiceTokenRepository(db_path)

    async def test_record_usage_updates_last_used_and_count(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """record_usage updates last_used_at and use_count."""
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

    async def test_record_usage_increments_count(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """record_usage increments use_count on multiple calls."""
        await repository.create(sample_token_record)

        await repository.record_usage("test-token-123")
        await repository.record_usage("test-token-123")
        await repository.record_usage("test-token-123")

        token = await repository.find_by_id("test-token-123")
        assert token is not None
        assert token.use_count == 3

    async def test_record_usage_without_ip_and_user_agent(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """record_usage works without ip and user_agent."""
        await repository.create(sample_token_record)

        await repository.record_usage("test-token-123")

        token = await repository.find_by_id("test-token-123")
        assert token is not None
        assert token.use_count == 1

    async def test_get_audit_log_returns_usage_entries(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """get_audit_log returns usage entries."""
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

    async def test_get_audit_log_respects_limit(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """get_audit_log respects the limit parameter."""
        await repository.create(sample_token_record)

        for _ in range(10):
            await repository.record_usage("test-token-123")

        log = await repository.get_audit_log("test-token-123", limit=5)
        assert len(log) == 5

    async def test_get_audit_log_empty_for_nonexistent_token(
        self, repository: SqliteServiceTokenRepository
    ) -> None:
        """get_audit_log returns empty list for nonexistent token."""
        log = await repository.get_audit_log("nonexistent-token")
        assert log == []

    async def test_record_audit_event(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """record_audit_event creates audit log entries."""
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

    async def test_record_audit_event_without_optional_fields(
        self,
        repository: SqliteServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """record_audit_event works without optional fields."""
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
