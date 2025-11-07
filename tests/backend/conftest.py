"""Shared pytest fixtures for backend tests."""

from __future__ import annotations
from datetime import UTC, datetime
import pytest
from orcheo_backend.app.authentication import ServiceTokenRecord


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
