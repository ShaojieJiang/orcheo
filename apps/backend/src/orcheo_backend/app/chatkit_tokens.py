"""Utilities for minting short-lived ChatKit session tokens."""

from __future__ import annotations
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4
import jwt
from orcheo.config import get_settings


class ChatKitTokenConfigurationError(RuntimeError):
    """Raised when ChatKit session token settings are missing or invalid."""


@dataclass(slots=True)
class ChatKitTokenSettings:
    """Resolved configuration for issuing ChatKit session tokens."""

    signing_key: str
    issuer: str
    audience: str
    ttl_seconds: int
    algorithm: str = "HS256"


class ChatKitSessionTokenIssuer:
    """Mint signed tokens for ChatKit client sessions."""

    def __init__(self, settings: ChatKitTokenSettings) -> None:
        """Store the issuer settings for future token minting."""
        self._settings = settings

    @property
    def settings(self) -> ChatKitTokenSettings:
        """Return the issuer configuration."""
        return self._settings

    def mint_session(
        self,
        *,
        subject: str,
        identity_type: str,
        token_id: str | None,
        workspace_ids: Iterable[str] | None,
        primary_workspace_id: str | None,
        workflow_id: UUID | None,
        scopes: Iterable[str],
        metadata: Mapping[str, Any] | None,
        user: Mapping[str, Any] | None,
        assistant: Mapping[str, Any] | None,
        extra: Mapping[str, Any] | None = None,
    ) -> tuple[str, datetime]:
        """Return a signed JWT and its expiry timestamp."""
        now = datetime.now(tz=UTC)
        expires_at = now + timedelta(seconds=self._settings.ttl_seconds)
        workspace_list = sorted({value for value in workspace_ids or [] if value})
        chatkit_claims: dict[str, Any] = {
            "workspace_id": primary_workspace_id,
            "workspace_ids": workspace_list,
            "workflow_id": str(workflow_id) if workflow_id else None,
            "scopes": sorted({scope for scope in scopes if scope}),
            "identity_type": identity_type,
            "token_id": token_id,
        }
        if metadata:
            chatkit_claims["metadata"] = metadata
        if user:
            chatkit_claims["user"] = user
        if assistant:
            chatkit_claims["assistant"] = assistant
        if extra:
            chatkit_claims.update(extra)

        claims: dict[str, Any] = {
            "iss": self._settings.issuer,
            "aud": self._settings.audience,
            "sub": subject,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": uuid4().hex,
            "chatkit": chatkit_claims,
        }

        token = jwt.encode(
            claims,
            self._settings.signing_key,
            algorithm=self._settings.algorithm,
        )
        return token, expires_at


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(str(value)) if value is not None else default
    except (TypeError, ValueError):
        return default


def load_chatkit_token_settings(*, refresh: bool = False) -> ChatKitTokenSettings:
    """Load ChatKit session token configuration from environment variables."""
    settings = get_settings(refresh=refresh)
    signing_key = _coerce_optional_str(settings.get("CHATKIT_TOKEN_SIGNING_KEY"))
    if not signing_key:
        raise ChatKitTokenConfigurationError(
            "ChatKit session token signing key is not configured",
        )

    issuer = _coerce_optional_str(settings.get("CHATKIT_TOKEN_ISSUER")) or (
        "orcheo.chatkit"
    )
    audience = _coerce_optional_str(settings.get("CHATKIT_TOKEN_AUDIENCE")) or "chatkit"
    ttl_seconds = _parse_int(settings.get("CHATKIT_TOKEN_TTL_SECONDS"), 300)
    algorithm = _coerce_optional_str(settings.get("CHATKIT_TOKEN_ALGORITHM")) or "HS256"

    return ChatKitTokenSettings(
        signing_key=signing_key,
        issuer=issuer,
        audience=audience,
        ttl_seconds=max(ttl_seconds, 60),
        algorithm=algorithm,
    )


_token_issuer_cache: dict[str, ChatKitSessionTokenIssuer | None] = {"issuer": None}


def get_chatkit_token_issuer(*, refresh: bool = False) -> ChatKitSessionTokenIssuer:
    """Return a cached ChatKitSessionTokenIssuer instance."""
    if refresh:
        _token_issuer_cache["issuer"] = None
    issuer = _token_issuer_cache.get("issuer")
    if issuer is None:
        settings = load_chatkit_token_settings(refresh=refresh)
        issuer = ChatKitSessionTokenIssuer(settings)
        _token_issuer_cache["issuer"] = issuer
    return issuer


def reset_chatkit_token_state() -> None:
    """Clear cached ChatKit token settings and refresh Dynaconf state."""
    _token_issuer_cache["issuer"] = None
    get_settings(refresh=True)


__all__ = [
    "ChatKitSessionTokenIssuer",
    "ChatKitTokenConfigurationError",
    "ChatKitTokenSettings",
    "reset_chatkit_token_state",
    "get_chatkit_token_issuer",
    "load_chatkit_token_settings",
]
