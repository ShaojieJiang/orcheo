"""Audit logging tests for the in-memory service token repository."""

from __future__ import annotations
import pytest
from orcheo_backend.app.authentication import ServiceTokenRecord
from orcheo_backend.app.service_token_repository import InMemoryServiceTokenRepository


pytestmark = pytest.mark.asyncio


class TestInMemoryServiceTokenRepositoryAudit:
    """Usage and audit tests for the in-memory repository."""

    @pytest.fixture
    def repository(self) -> InMemoryServiceTokenRepository:
        """Create an in-memory repository instance."""
        return InMemoryServiceTokenRepository()

    async def test_record_usage(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """record_usage updates token and creates audit log."""
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

    async def test_record_usage_for_nonexistent_token(
        self, repository: InMemoryServiceTokenRepository
    ) -> None:
        """record_usage handles nonexistent token gracefully."""
        await repository.record_usage("nonexistent-token")

        log = await repository.get_audit_log("nonexistent-token")
        assert len(log) == 1

    async def test_get_audit_log_limit(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """get_audit_log respects limit parameter."""
        await repository.create(sample_token_record)

        for _ in range(10):
            await repository.record_usage("test-token-123")

        log = await repository.get_audit_log("test-token-123", limit=5)
        assert len(log) == 5

    async def test_record_audit_event(
        self,
        repository: InMemoryServiceTokenRepository,
        sample_token_record: ServiceTokenRecord,
    ) -> None:
        """record_audit_event creates audit entries."""
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
