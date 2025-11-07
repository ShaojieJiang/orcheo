"""OAuth token helpers for credential metadata."""

from __future__ import annotations
from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any
from pydantic import model_validator
from orcheo.models.base import OrcheoBaseModel
from orcheo.models.credential_crypto import CredentialCipher, EncryptionEnvelope


__all__ = ["OAuthTokenPayload", "OAuthTokenSecrets"]


class OAuthTokenSecrets(OrcheoBaseModel):
    """Plaintext representation of OAuth tokens used by providers."""

    access_token: str | None = None
    refresh_token: str | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _normalize_expiry(self) -> OAuthTokenSecrets:
        if self.expires_at and self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=UTC))
        return self


class OAuthTokenPayload(OrcheoBaseModel):
    """Encrypted storage for OAuth token secrets."""

    access_token: EncryptionEnvelope | None = None
    refresh_token: EncryptionEnvelope | None = None
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def _normalize_expiry(self) -> OAuthTokenPayload:
        if self.expires_at and self.expires_at.tzinfo is None:
            object.__setattr__(self, "expires_at", self.expires_at.replace(tzinfo=UTC))
        return self

    @classmethod
    def from_secrets(
        cls, *, cipher: CredentialCipher, secrets: OAuthTokenSecrets | None
    ) -> OAuthTokenPayload:
        """Create an encrypted payload from plaintext OAuth tokens."""
        if secrets is None:
            return cls()
        return cls(
            access_token=cipher.encrypt(secrets.access_token)
            if secrets.access_token
            else None,
            refresh_token=cipher.encrypt(secrets.refresh_token)
            if secrets.refresh_token
            else None,
            expires_at=secrets.expires_at,
        )

    def reveal(self, *, cipher: CredentialCipher) -> OAuthTokenSecrets:
        """Return decrypted OAuth tokens from the encrypted payload."""
        return OAuthTokenSecrets(
            access_token=self.access_token.decrypt(cipher)
            if self.access_token
            else None,
            refresh_token=self.refresh_token.decrypt(cipher)
            if self.refresh_token
            else None,
            expires_at=self.expires_at,
        )

    def redact(self) -> MutableMapping[str, Any]:
        """Return redacted metadata describing stored OAuth tokens."""
        return {
            "has_access_token": self.access_token is not None,
            "has_refresh_token": self.refresh_token is not None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
