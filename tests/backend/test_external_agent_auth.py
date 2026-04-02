from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
from orcheo.models import CredentialScope
from orcheo_backend.app.external_agent_auth import (
    CLAUDE_CODE_OAUTH_TOKEN_CREDENTIAL_NAME,
    CODEX_AUTH_JSON_CREDENTIAL_NAME,
    CODEX_AUTH_JSON_ENV_VAR,
    load_external_agent_vault_environment,
    reveal_external_agent_secret,
    upsert_external_agent_secret,
)


def test_upsert_external_agent_secret_updates_first_match_and_deletes_duplicates() -> (
    None
):
    vault = MagicMock()
    first = SimpleNamespace(id=uuid4(), name="CODEX_AUTH_JSON")
    duplicate = SimpleNamespace(id=uuid4(), name="CODEX_AUTH_JSON")
    vault.list_all_credentials.return_value = [first, duplicate]

    upsert_external_agent_secret(
        vault,
        credential_name="CODEX_AUTH_JSON",
        provider="codex",
        secret="{}",
    )

    vault.update_credential.assert_called_once_with(
        credential_id=first.id,
        actor="external_agent_worker",
        provider="codex",
        secret="{}",
        scope=CredentialScope.unrestricted(),
    )
    vault.delete_credential.assert_called_once_with(duplicate.id)


def test_load_external_agent_vault_environment_materializes_all_secrets() -> None:
    vault = MagicMock()
    claude = SimpleNamespace(
        id=uuid4(),
        name=CLAUDE_CODE_OAUTH_TOKEN_CREDENTIAL_NAME,
    )
    codex = SimpleNamespace(
        id=uuid4(),
        name=CODEX_AUTH_JSON_CREDENTIAL_NAME,
    )
    vault.list_all_credentials.return_value = [claude, codex]

    def reveal_secret(*, credential_id: object) -> str | None:
        if credential_id == claude.id:
            return "claude-token"
        if credential_id == codex.id:
            return '{"auth": "json"}'
        raise AssertionError("unexpected credential id")

    vault.reveal_secret.side_effect = reveal_secret

    environ = load_external_agent_vault_environment(vault)

    assert environ == {
        "CLAUDE_CODE_OAUTH_TOKEN": "claude-token",
        CODEX_AUTH_JSON_ENV_VAR: '{"auth": "json"}',
    }


def test_reveal_external_agent_secret_returns_none_when_missing() -> None:
    vault = MagicMock()
    vault.list_all_credentials.return_value = []

    assert (
        reveal_external_agent_secret(vault, CLAUDE_CODE_OAUTH_TOKEN_CREDENTIAL_NAME)
        is None
    )
    vault.reveal_secret.assert_not_called()
