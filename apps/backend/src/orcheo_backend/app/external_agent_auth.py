"""Vault-backed auth helpers for worker-scoped external agent providers."""

from __future__ import annotations
from typing import Final
from orcheo.external_agents.providers.gemini import (
    GEMINI_GOOGLE_ACCOUNTS_JSON_ENV_VAR,
    GEMINI_OAUTH_CREDS_JSON_ENV_VAR,
    GEMINI_STATE_JSON_ENV_VAR,
)
from orcheo.models import CredentialMetadata, CredentialScope
from orcheo.vault import BaseCredentialVault


CLAUDE_CODE_OAUTH_TOKEN_CREDENTIAL_NAME: Final[str] = "CLAUDE_CODE_OAUTH_TOKEN"
CODEX_AUTH_JSON_CREDENTIAL_NAME: Final[str] = "CODEX_AUTH_JSON"
CODEX_AUTH_JSON_ENV_VAR: Final[str] = "CODEX_AUTH_JSON"
GEMINI_GOOGLE_ACCOUNTS_JSON_CREDENTIAL_NAME: Final[str] = "GEMINI_GOOGLE_ACCOUNTS_JSON"
GEMINI_STATE_JSON_CREDENTIAL_NAME: Final[str] = "GEMINI_STATE_JSON"
GEMINI_OAUTH_CREDS_JSON_CREDENTIAL_NAME: Final[str] = "GEMINI_OAUTH_CREDS_JSON"
EXTERNAL_AGENT_VAULT_ACTOR: Final[str] = "external_agent_worker"


def load_external_agent_vault_environment(
    vault: BaseCredentialVault,
) -> dict[str, str]:
    """Return environment overrides materialized from the configured vault."""
    environ: dict[str, str] = {}
    claude_token = reveal_external_agent_secret(
        vault,
        CLAUDE_CODE_OAUTH_TOKEN_CREDENTIAL_NAME,
    )
    if claude_token:
        environ["CLAUDE_CODE_OAUTH_TOKEN"] = claude_token

    codex_auth_json = reveal_external_agent_secret(
        vault,
        CODEX_AUTH_JSON_CREDENTIAL_NAME,
    )
    if codex_auth_json:
        environ[CODEX_AUTH_JSON_ENV_VAR] = codex_auth_json

    gemini_google_accounts_json = reveal_external_agent_secret(
        vault,
        GEMINI_GOOGLE_ACCOUNTS_JSON_CREDENTIAL_NAME,
    )
    if gemini_google_accounts_json:
        environ[GEMINI_GOOGLE_ACCOUNTS_JSON_ENV_VAR] = gemini_google_accounts_json

    gemini_state_json = reveal_external_agent_secret(
        vault,
        GEMINI_STATE_JSON_CREDENTIAL_NAME,
    )
    if gemini_state_json:
        environ[GEMINI_STATE_JSON_ENV_VAR] = gemini_state_json

    gemini_oauth_creds_json = reveal_external_agent_secret(
        vault,
        GEMINI_OAUTH_CREDS_JSON_CREDENTIAL_NAME,
    )
    if gemini_oauth_creds_json:
        environ[GEMINI_OAUTH_CREDS_JSON_ENV_VAR] = gemini_oauth_creds_json
    return environ


def reveal_external_agent_secret(
    vault: BaseCredentialVault,
    credential_name: str,
) -> str | None:
    """Return the secret for ``credential_name`` when it exists."""
    metadata = _find_named_credential(vault, credential_name)
    if metadata is None:
        return None
    return vault.reveal_secret(credential_id=metadata.id)


def upsert_external_agent_secret(
    vault: BaseCredentialVault,
    *,
    credential_name: str,
    provider: str,
    secret: str,
    actor: str = EXTERNAL_AGENT_VAULT_ACTOR,
) -> None:
    """Create or update one unrestricted external-agent secret."""
    matches = _find_named_credentials(vault, credential_name)
    existing = matches[0] if matches else None
    if existing is None:
        vault.create_credential(
            name=credential_name,
            provider=provider,
            scopes=["worker", "external-agent", provider],
            secret=secret,
            actor=actor,
            scope=CredentialScope.unrestricted(),
        )
        return

    vault.update_credential(
        credential_id=existing.id,
        actor=actor,
        provider=provider,
        secret=secret,
        scope=CredentialScope.unrestricted(),
    )
    for duplicate in matches[1:]:
        vault.delete_credential(duplicate.id)


def delete_external_agent_secret(
    vault: BaseCredentialVault,
    *,
    credential_name: str,
) -> bool:
    """Delete all stored secrets for ``credential_name`` if they exist."""
    matches = _find_named_credentials(vault, credential_name)
    deleted = False
    for metadata in matches:
        vault.delete_credential(metadata.id)
        deleted = True
    return deleted


def _find_named_credential(
    vault: BaseCredentialVault,
    credential_name: str,
) -> CredentialMetadata | None:
    matches = _find_named_credentials(vault, credential_name)
    return matches[0] if matches else None


def _find_named_credentials(
    vault: BaseCredentialVault,
    credential_name: str,
) -> list[CredentialMetadata]:
    normalized_name = credential_name.strip().lower()
    return [
        metadata
        for metadata in vault.list_all_credentials()
        if metadata.name.strip().lower() == normalized_name
    ]


__all__ = [
    "CLAUDE_CODE_OAUTH_TOKEN_CREDENTIAL_NAME",
    "CODEX_AUTH_JSON_CREDENTIAL_NAME",
    "CODEX_AUTH_JSON_ENV_VAR",
    "GEMINI_GOOGLE_ACCOUNTS_JSON_CREDENTIAL_NAME",
    "GEMINI_STATE_JSON_CREDENTIAL_NAME",
    "GEMINI_OAUTH_CREDS_JSON_CREDENTIAL_NAME",
    "EXTERNAL_AGENT_VAULT_ACTOR",
    "delete_external_agent_secret",
    "load_external_agent_vault_environment",
    "reveal_external_agent_secret",
    "upsert_external_agent_secret",
]
