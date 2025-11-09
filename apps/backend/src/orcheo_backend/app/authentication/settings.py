from __future__ import annotations
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from orcheo.config import get_settings
from .utils import coerce_str_items, parse_timestamp


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthSettings:
    """Resolved authentication configuration for the backend."""

    mode: str
    jwt_secret: str | None
    jwks_url: str | None
    jwks_static: tuple[Mapping[str, Any], ...]
    jwks_cache_ttl: int
    jwks_timeout: float
    allowed_algorithms: tuple[str, ...]
    audiences: tuple[str, ...]
    issuer: str | None
    rate_limit_ip: int
    rate_limit_identity: int
    rate_limit_interval: int
    service_token_db_path: str | None
    bootstrap_service_token: str | None = None
    bootstrap_token_scopes: frozenset[str] = field(default_factory=frozenset)
    bootstrap_token_expires_at: datetime | None = None
    dev_login_enabled: bool = False
    dev_login_cookie_name: str | None = None
    dev_login_scopes: tuple[str, ...] = field(default_factory=tuple)
    dev_login_workspace_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def enforce(self) -> bool:
        """Return True when authentication should be enforced for requests."""
        if self.mode == "disabled":
            return False
        if self.mode == "required":
            return True
        return bool(
            self.jwt_secret
            or self.jwks_url
            or self.jwks_static
            or self.service_token_db_path
            or self.bootstrap_service_token
        )


_DEFAULT_ALGORITHMS: tuple[str, ...] = ("RS256", "HS256")
_DEV_DEFAULT_SCOPES: tuple[str, ...] = (
    "workflows:read",
    "workflows:write",
    "workflows:execute",
    "vault:read",
    "vault:write",
)


def load_auth_settings(*, refresh: bool = False) -> AuthSettings:
    """Load authentication settings from Dynaconf and environment variables."""
    settings = get_settings(refresh=refresh)
    mode = _coerce_mode(settings.get("AUTH_MODE", "optional"))
    jwt_secret = _coerce_optional_str(settings.get("AUTH_JWT_SECRET"))
    jwks_url = _coerce_optional_str(settings.get("AUTH_JWKS_URL"))
    jwks_cache_ttl = _parse_int(settings.get("AUTH_JWKS_CACHE_TTL"), 300)
    jwks_timeout = _parse_float(settings.get("AUTH_JWKS_TIMEOUT"), 5.0)

    jwks_raw = settings.get("AUTH_JWKS") or settings.get("AUTH_JWKS_STATIC")
    jwks_static = tuple(dict(item) for item in _parse_jwks(jwks_raw))

    allowed_algorithms = _parse_str_sequence(settings.get("AUTH_ALLOWED_ALGORITHMS"))
    if not allowed_algorithms:
        allowed_algorithms = _DEFAULT_ALGORITHMS

    audiences = _parse_str_sequence(settings.get("AUTH_AUDIENCE"))
    issuer = _coerce_optional_str(settings.get("AUTH_ISSUER"))

    service_token_db_path = _coerce_optional_str(
        settings.get("AUTH_SERVICE_TOKEN_DB_PATH")
    )
    if not service_token_db_path:
        repo_path = settings.get("ORCHEO_REPOSITORY_SQLITE_PATH")
        if repo_path:
            db_path = Path(str(repo_path)).expanduser()
            service_token_db_path = str(db_path.parent / "service_tokens.sqlite")

    rate_limit_ip = _parse_int(settings.get("AUTH_RATE_LIMIT_IP"), 0)
    rate_limit_identity = _parse_int(settings.get("AUTH_RATE_LIMIT_IDENTITY"), 0)
    rate_limit_interval = _parse_int(settings.get("AUTH_RATE_LIMIT_INTERVAL"), 60)

    bootstrap_service_token = _coerce_optional_str(
        settings.get("AUTH_BOOTSTRAP_SERVICE_TOKEN")
    )
    bootstrap_token_scopes_raw = settings.get("AUTH_BOOTSTRAP_TOKEN_SCOPES")
    if bootstrap_token_scopes_raw:
        bootstrap_token_scopes = frozenset(
            _parse_str_sequence(bootstrap_token_scopes_raw)
        )
    else:
        bootstrap_token_scopes = frozenset(
            [
                "admin:tokens:read",
                "admin:tokens:write",
                "workflows:read",
                "workflows:write",
                "workflows:execute",
                "vault:read",
                "vault:write",
            ]
        )

    bootstrap_token_expires_at_raw = settings.get("AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT")
    bootstrap_token_expires_at = parse_timestamp(bootstrap_token_expires_at_raw)
    if bootstrap_token_expires_at_raw and bootstrap_token_expires_at is None:
        logger.warning(  # pragma: no cover - defensive
            "AUTH_BOOTSTRAP_TOKEN_EXPIRES_AT could not be parsed; expected ISO 8601 "
            "or UNIX timestamp"
        )

    if bootstrap_service_token:
        logger.warning(
            "Bootstrap service token is configured. This should only be used for "
            "initial setup and should be removed after creating persistent tokens."
        )

    if mode == "required" and not (
        jwt_secret
        or jwks_url
        or jwks_static
        or service_token_db_path
        or bootstrap_service_token
    ):
        logger.warning(
            "AUTH_MODE=required but no authentication credentials are configured; "
            "all requests will be rejected",
        )

    dev_login_enabled = _parse_bool(settings.get("AUTH_DEV_LOGIN_ENABLED"), False)
    dev_cookie_name: str | None = None
    dev_scopes: tuple[str, ...] = ()
    dev_workspace_ids: tuple[str, ...] = ()
    if dev_login_enabled:
        dev_cookie_name = (
            _coerce_optional_str(settings.get("AUTH_DEV_COOKIE_NAME"))
            or "orcheo_dev_session"
        )
        dev_scopes = _parse_str_sequence(settings.get("AUTH_DEV_SCOPES"))
        if not dev_scopes:
            dev_scopes = _DEV_DEFAULT_SCOPES
        dev_workspace_ids = _parse_str_sequence(settings.get("AUTH_DEV_WORKSPACE_IDS"))

    return AuthSettings(
        mode=mode,
        jwt_secret=jwt_secret,
        jwks_url=jwks_url,
        jwks_static=tuple(jwks_static),
        jwks_cache_ttl=jwks_cache_ttl,
        jwks_timeout=jwks_timeout,
        allowed_algorithms=tuple(allowed_algorithms),
        audiences=tuple(audiences),
        issuer=issuer,
        service_token_db_path=service_token_db_path,
        bootstrap_service_token=bootstrap_service_token,
        bootstrap_token_scopes=bootstrap_token_scopes,
        bootstrap_token_expires_at=bootstrap_token_expires_at,
        rate_limit_ip=rate_limit_ip,
        rate_limit_identity=rate_limit_identity,
        rate_limit_interval=rate_limit_interval,
        dev_login_enabled=dev_login_enabled,
        dev_login_cookie_name=dev_cookie_name,
        dev_login_scopes=tuple(dev_scopes),
        dev_login_workspace_ids=tuple(dev_workspace_ids),
    )


def _parse_jwks(raw: Any) -> list[Mapping[str, Any]]:
    """Parse JWKS configuration supporting string, mapping, or sequences."""
    data = raw
    if isinstance(raw, str):
        candidate = raw.strip()
        if not candidate:
            return []
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            logger.warning("Failed to parse AUTH_JWKS value as JSON")
            return []

    if isinstance(data, Mapping):
        keys = data.get("keys")
        return _normalize_jwk_list(keys)
    if isinstance(data, Sequence):
        return _normalize_jwk_list(data)
    return []


def _normalize_jwk_list(value: Any) -> list[Mapping[str, Any]]:
    """Return a normalized list of JWKS dictionaries."""
    if not isinstance(value, Sequence):
        return []
    normalized: list[Mapping[str, Any]] = []
    for item in value:
        if isinstance(item, Mapping):
            normalized.append(dict(item))
    return normalized


def _coerce_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    candidate = str(value).strip()
    return candidate or None


def _coerce_mode(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"disabled", "required", "optional"}:
            return lowered
    return "optional"


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _parse_float(value: Any, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return default


def _parse_int(value: Any, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return default


def _parse_str_sequence(value: Any) -> tuple[str, ...]:
    items = coerce_str_items(value)
    return tuple(item for item in items if item)
