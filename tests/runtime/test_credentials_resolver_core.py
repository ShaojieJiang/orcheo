"""Core CredentialResolver behavior tests."""

from __future__ import annotations
from uuid import uuid4
import pytest
from orcheo.models import CredentialAccessContext, CredentialScope
from orcheo.runtime.credentials import (
    CredentialReference,
    CredentialReferenceNotFoundError,
    CredentialResolver,
    DuplicateCredentialReferenceError,
    UnknownCredentialPayloadError,
    credential_ref,
    credential_resolution,
    get_active_credential_resolver,
)
from orcheo.vault import DuplicateCredentialNameError, InMemoryCredentialVault
from tests.runtime.credential_test_helpers import create_vault_with_secret


def test_resolver_caches_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    vault = create_vault_with_secret()
    resolver = CredentialResolver(vault)
    reference = CredentialReference(identifier="telegram_bot")

    reveal_calls: list[int] = []
    original_reveal = vault.reveal_secret

    def _wrapped(**kwargs):  # type: ignore[no-untyped-def]
        reveal_calls.append(1)
        return original_reveal(**kwargs)

    monkeypatch.setattr(vault, "reveal_secret", _wrapped)

    with credential_resolution(resolver):
        assert resolver.resolve(reference) == "s3cret"
        assert resolver.resolve(reference) == "s3cret"

    assert len(reveal_calls) == 1


def test_resolver_rejects_unknown_payload() -> None:
    vault = create_vault_with_secret()
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        with pytest.raises(UnknownCredentialPayloadError):
            resolver.resolve(credential_ref("telegram_bot", "oauth"))
        with pytest.raises(UnknownCredentialPayloadError):
            resolver.resolve(credential_ref("telegram_bot", "secret.value"))
        with pytest.raises(UnknownCredentialPayloadError):
            resolver.resolve(credential_ref("telegram_bot", "api_key"))


def test_resolver_rejects_duplicate_name_references(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vault = create_vault_with_secret()
    resolver = CredentialResolver(vault)
    metadata = vault.list_credentials(context=None)[0]
    duplicate = metadata.model_copy(update={"id": uuid4()}, deep=True)
    metadata_by_id = {metadata.id: metadata, duplicate.id: duplicate}
    metadata_by_name = {metadata.name: [metadata, duplicate]}

    monkeypatch.setattr(
        resolver,
        "_load_metadata_index",
        lambda: (metadata_by_id, metadata_by_name),
    )

    with pytest.raises(DuplicateCredentialReferenceError):
        resolver.resolve(credential_ref(metadata.name))


def test_vault_rejects_duplicate_names() -> None:
    vault = InMemoryCredentialVault()
    vault.create_credential(
        name="dup",
        provider="telegram",
        scopes=["bot"],
        secret="value",
        actor="tester",
        scope=CredentialScope.unrestricted(),
    )
    with pytest.raises(DuplicateCredentialNameError):
        vault.create_credential(
            name="dup",
            provider="telegram",
            scopes=["bot"],
            secret="another",
            actor="tester",
            scope=CredentialScope.unrestricted(),
        )


def test_resolver_missing_reference() -> None:
    vault = create_vault_with_secret()
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        with pytest.raises(CredentialReferenceNotFoundError):
            resolver.resolve(credential_ref("missing"))


def test_get_active_resolver_returns_current_instance() -> None:
    vault = create_vault_with_secret()
    resolver = CredentialResolver(vault)
    assert get_active_credential_resolver() is None
    with credential_resolution(resolver):
        assert get_active_credential_resolver() is resolver
    assert get_active_credential_resolver() is None


def test_credential_resolution_allows_null_resolver() -> None:
    with credential_resolution(None) as active:
        assert active is None
        assert get_active_credential_resolver() is None


def test_resolver_respects_context_scope() -> None:
    vault = InMemoryCredentialVault()
    allowed = uuid4()
    denied = uuid4()
    vault.create_credential(
        name="scoped",
        provider="telegram",
        scopes=["bot"],
        secret="token",
        actor="tester",
        scope=CredentialScope.for_workflows(allowed),
    )
    resolver = CredentialResolver(
        vault, context=CredentialAccessContext(workflow_id=allowed)
    )
    with credential_resolution(resolver):
        assert resolver.resolve(credential_ref("scoped")) == "token"

    restricted_resolver = CredentialResolver(
        vault, context=CredentialAccessContext(workflow_id=denied)
    )
    with credential_resolution(restricted_resolver):
        with pytest.raises(CredentialReferenceNotFoundError):
            restricted_resolver.resolve(credential_ref("scoped"))


def test_resolver_allows_uuid_identifiers() -> None:
    vault = create_vault_with_secret(secret="token")
    metadata = vault.list_credentials()[0]
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        value = resolver.resolve(CredentialReference(identifier=str(metadata.id)))
        assert value == "token"


def test_resolver_handles_uuid_like_name() -> None:
    uuid_name = str(uuid4())
    vault = InMemoryCredentialVault()
    vault.create_credential(
        name=uuid_name,
        provider="telegram",
        scopes=["bot"],
        secret="token",
        actor="tester",
        scope=CredentialScope.unrestricted(),
    )
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        assert resolver.resolve(credential_ref(uuid_name)) == "token"


def test_resolver_accepts_explicit_empty_payload_path() -> None:
    vault = create_vault_with_secret(secret="token")
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        value = resolver.resolve(CredentialReference("telegram_bot", ()))
        assert value == "token"
