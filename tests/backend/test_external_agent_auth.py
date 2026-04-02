from __future__ import annotations
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
from orcheo.models import CredentialScope
from orcheo_backend.app.external_agent_auth import upsert_external_agent_secret


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
