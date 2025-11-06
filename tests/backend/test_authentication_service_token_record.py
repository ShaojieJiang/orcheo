"""ServiceTokenRecord behaviour tests."""

from __future__ import annotations
import hashlib
from datetime import UTC, datetime, timedelta
from orcheo_backend.app.authentication import ServiceTokenRecord


def test_service_token_record_matches() -> None:
    """ServiceTokenRecord.matches() validates tokens against the hash."""

    token = "my-secret-token"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    record = ServiceTokenRecord(identifier="test", secret_hash=digest)

    assert record.matches(token)
    assert not record.matches("wrong-token")


def test_service_token_record_is_revoked() -> None:
    """ServiceTokenRecord.is_revoked() checks revocation status."""

    record = ServiceTokenRecord(identifier="test", secret_hash="hash123")
    assert not record.is_revoked()

    revoked_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        revoked_at=datetime.now(tz=UTC),
    )
    assert revoked_record.is_revoked()


def test_service_token_record_is_expired() -> None:
    """ServiceTokenRecord.is_expired() checks expiry status."""

    # No expiry
    record = ServiceTokenRecord(identifier="test", secret_hash="hash123")
    assert not record.is_expired()

    # Expired
    expired_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
    )
    assert expired_record.is_expired()

    # Not yet expired
    future_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
    )
    assert not future_record.is_expired()


def test_service_token_record_is_active() -> None:
    """ServiceTokenRecord.is_active() combines revocation and expiry checks."""

    # Active
    record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
    )
    assert record.is_active()

    # Revoked
    revoked_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        revoked_at=datetime.now(tz=UTC),
    )
    assert not revoked_record.is_active()

    # Expired
    expired_record = ServiceTokenRecord(
        identifier="test",
        secret_hash="hash123",
        expires_at=datetime.now(tz=UTC) - timedelta(hours=1),
    )
    assert not expired_record.is_active()
