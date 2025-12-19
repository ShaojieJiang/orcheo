"""Factories for repository, vault, and credential service instances."""

from __future__ import annotations
import os
import secrets
from pathlib import Path
from typing import Any, cast
from dynaconf import Dynaconf
from orcheo.models import AesGcmCredentialCipher
from orcheo.vault import (
    BaseCredentialVault,
    FileCredentialVault,
    InMemoryCredentialVault,
)
from orcheo.vault.oauth import OAuthCredentialService
from orcheo_backend.app.agentensor.checkpoint_store import (
    InMemoryAgentensorCheckpointStore,
    SqliteAgentensorCheckpointStore,
)
from orcheo_backend.app.history import (
    InMemoryRunHistoryStore,
    RunHistoryStore,
    SqliteRunHistoryStore,
)
from orcheo_backend.app.repository import (
    InMemoryWorkflowRepository,
    WorkflowRepository,
)
from orcheo_backend.app.repository_sqlite import SqliteWorkflowRepository


def settings_value(
    settings: Dynaconf,
    *,
    attr_path: str | None,
    env_key: str,
    default: Any,
) -> Any:
    """Return a configuration value supporting Dynaconf attribute access."""
    if hasattr(settings, "get"):
        try:
            value = settings.get(env_key, default)  # type: ignore[call-arg]
        except TypeError:  # pragma: no cover - defensive fallback
            value = default
        return cast(Any, value)

    if attr_path:
        current: object = settings
        for part in attr_path.split("."):
            if not hasattr(current, part):
                break
            current = getattr(current, part)
        else:
            return cast(Any, current)

    return default


def ensure_file_vault_key(path: Path, provided_key: str | None) -> str:
    """Load or generate the encryption key for the file-backed credential vault."""
    if provided_key:
        return provided_key

    key_path = path.with_name(f"{path.stem}.key")
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        key = key_path.read_text(encoding="utf-8").strip()
        if key:
            return key

    key = secrets.token_hex(32)
    key_path.write_text(key, encoding="utf-8")
    try:
        os.chmod(key_path, 0o600)
    except (PermissionError, NotImplementedError, OSError):
        pass
    return key


def create_vault(settings: Dynaconf) -> BaseCredentialVault:
    """Create a credential vault based on configured backend."""
    backend = cast(
        str,
        settings_value(
            settings,
            attr_path="vault.backend",
            env_key="VAULT_BACKEND",
            default="file",
        ),
    )
    key = cast(
        str | None,
        settings_value(
            settings,
            attr_path="vault.encryption_key",
            env_key="VAULT_ENCRYPTION_KEY",
            default=None,
        ),
    )
    if backend == "inmemory":
        encryption_key = key or secrets.token_hex(32)
        cipher = AesGcmCredentialCipher(key=encryption_key)
        return InMemoryCredentialVault(cipher=cipher)
    if backend == "file":
        local_path = cast(
            str,
            settings_value(
                settings,
                attr_path="vault.local_path",
                env_key="VAULT_LOCAL_PATH",
                default=".orcheo/vault.sqlite",
            ),
        )
        path = Path(local_path).expanduser()
        encryption_key = ensure_file_vault_key(path, key)
        cipher = AesGcmCredentialCipher(key=encryption_key)
        return FileCredentialVault(path, cipher=cipher)
    msg = "Vault backend 'aws_kms' is not supported in this environment."
    raise ValueError(msg)


def ensure_credential_service(
    settings: Dynaconf,
    vault: BaseCredentialVault,
) -> OAuthCredentialService:
    """Initialise the OAuth credential service with configured TTL."""
    token_ttl = cast(
        int,
        settings_value(
            settings,
            attr_path="vault.token_ttl_seconds",
            env_key="VAULT_TOKEN_TTL_SECONDS",
            default=3600,
        ),
    )
    return OAuthCredentialService(vault, token_ttl_seconds=token_ttl)


def create_repository(
    settings: Dynaconf,
    credential_service: OAuthCredentialService,
    history_store_ref: dict[str, RunHistoryStore],
    checkpoint_store_ref: dict[str, object] | None = None,
) -> WorkflowRepository:
    """Create the workflow repository using configured backend."""
    backend = cast(
        str,
        settings_value(
            settings,
            attr_path="repository_backend",
            env_key="REPOSITORY_BACKEND",
            default="sqlite",
        ),
    )

    if backend == "sqlite":
        sqlite_path = cast(
            str,
            settings_value(
                settings,
                attr_path="repository_sqlite_path",
                env_key="REPOSITORY_SQLITE_PATH",
                default="~/.orcheo/workflows.sqlite",
            ),
        )
        history_store_ref["store"] = SqliteRunHistoryStore(sqlite_path)
        if checkpoint_store_ref is not None:  # pragma: no branch
            checkpoint_store_ref["store"] = SqliteAgentensorCheckpointStore(sqlite_path)
        return SqliteWorkflowRepository(
            sqlite_path,
            credential_service=credential_service,
        )
    if backend == "inmemory":
        history_store_ref["store"] = InMemoryRunHistoryStore()
        if checkpoint_store_ref is not None:  # pragma: no branch
            checkpoint_store_ref["store"] = InMemoryAgentensorCheckpointStore()
        return InMemoryWorkflowRepository(credential_service=credential_service)
    msg = "Unsupported repository backend configured."
    raise ValueError(msg)


__all__ = [
    "create_repository",
    "create_vault",
    "ensure_credential_service",
    "ensure_file_vault_key",
    "settings_value",
]
