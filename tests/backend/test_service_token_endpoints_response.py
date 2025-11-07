"""Tests for transforming service token records into API responses."""

from __future__ import annotations
from datetime import UTC, datetime
from orcheo_backend.app.authentication import ServiceTokenRecord
from orcheo_backend.app.service_token_endpoints import _record_to_response


def test_record_to_response():
    """_record_to_response should include all relevant metadata."""
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
    """_record_to_response should surface revocation information."""
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
