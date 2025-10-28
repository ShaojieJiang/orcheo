"""Tests for runtime credential resolution helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from orcheo.graph.state import State
from orcheo.models import (
    CredentialAccessContext,
    CredentialKind,
    CredentialScope,
    OAuthTokenSecrets,
)
from orcheo.nodes.logic import SetVariableNode
from orcheo.runtime.credentials import (
    CredentialReference,
    CredentialReferenceNotFoundError,
    CredentialResolver,
    CredentialResolverUnavailableError,
    DuplicateCredentialReferenceError,
    UnknownCredentialPayloadError,
    credential_ref,
    credential_resolution,
    get_active_credential_resolver,
    parse_credential_reference,
)
from orcheo.vault import InMemoryCredentialVault


def _create_vault_with_secret(secret: str = "s3cret") -> InMemoryCredentialVault:
    vault = InMemoryCredentialVault()
    vault.create_credential(
        name="telegram_bot",
        provider="telegram",
        scopes=["bot"],
        secret=secret,
        actor="tester",
        scope=CredentialScope.unrestricted(),
    )
    return vault


def test_parse_credential_reference_round_trip() -> None:
    reference = parse_credential_reference("[[telegram_bot]]")
    assert reference is not None
    assert reference.identifier == "telegram_bot"
    assert reference.payload_path == ("secret",)

    oauth_reference = parse_credential_reference("[[telegram_bot#oauth.access_token]]")
    assert oauth_reference is not None
    assert oauth_reference.payload_path == ("oauth", "access_token")

    assert parse_credential_reference("[[  ]]") is None
    assert parse_credential_reference("plain text") is None
    assert parse_credential_reference("[[#oauth]]") is None


def test_credential_ref_helper_accepts_iterable_payload() -> None:
    reference = credential_ref("telegram_bot", ["oauth", "refresh_token"])
    assert reference.payload_path == ("oauth", "refresh_token")


def test_credential_ref_rejects_blank_identifier() -> None:
    with pytest.raises(ValueError):
        credential_ref("   ")


def test_credential_ref_defaults_to_secret_when_payload_blank() -> None:
    reference = credential_ref("telegram_bot", " ")
    assert reference.payload_path == ("secret",)


def test_resolver_caches_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    vault = _create_vault_with_secret()
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


def test_resolver_supports_oauth_payload() -> None:
    vault = InMemoryCredentialVault()
    expires_at = datetime.now(tz=UTC) + timedelta(hours=1)
    vault.create_credential(
        name="oauth_bot",
        provider="oauth",  # pragma: no cover - descriptive value
        scopes=["bot"],
        secret="ignored",  # pragma: no cover - required field
        actor="tester",
        kind=CredentialKind.OAUTH,
        scope=CredentialScope.unrestricted(),
        oauth_tokens=OAuthTokenSecrets(
            access_token="access", refresh_token="refresh", expires_at=expires_at
        ),
    )
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        tokens = resolver.resolve(credential_ref("oauth_bot", "oauth"))
        assert tokens.access_token == "access"
        assert (
            resolver.resolve(credential_ref("oauth_bot", "oauth.access_token"))
            == "access"
        )
        assert (
            resolver.resolve(credential_ref("oauth_bot", "oauth.expires_at"))
            == expires_at
        )


def test_resolver_returns_none_when_oauth_tokens_missing() -> None:
    vault = InMemoryCredentialVault()
    metadata = vault.create_credential(
        name="oauth_bot",
        provider="oauth",
        scopes=["bot"],
        secret="ignored",
        actor="tester",
        kind=CredentialKind.OAUTH,
        scope=CredentialScope.unrestricted(),
    )
    vault.update_oauth_tokens(
        credential_id=metadata.id,
        tokens=None,
        actor="tester",
    )
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        assert resolver.resolve(credential_ref("oauth_bot", "oauth")) is None


def test_resolver_rejects_unknown_payload() -> None:
    vault = _create_vault_with_secret()
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        with pytest.raises(UnknownCredentialPayloadError):
            resolver.resolve(credential_ref("telegram_bot", "oauth"))
        with pytest.raises(UnknownCredentialPayloadError):
            resolver.resolve(credential_ref("telegram_bot", "secret.value"))
        with pytest.raises(UnknownCredentialPayloadError):
            resolver.resolve(credential_ref("telegram_bot", "api_key"))


def test_resolver_detects_duplicate_names() -> None:
    vault = InMemoryCredentialVault()
    for scope in (CredentialScope.unrestricted(), CredentialScope.unrestricted()):
        vault.create_credential(
            name="dup",
            provider="telegram",
            scopes=["bot"],
            secret="value",
            actor="tester",
            scope=scope,
        )
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        with pytest.raises(DuplicateCredentialReferenceError):
            resolver.resolve(credential_ref("dup"))


def test_resolver_missing_reference() -> None:
    vault = _create_vault_with_secret()
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        with pytest.raises(CredentialReferenceNotFoundError):
            resolver.resolve(credential_ref("missing"))


def test_get_active_resolver_returns_current_instance() -> None:
    vault = _create_vault_with_secret()
    resolver = CredentialResolver(vault)
    assert get_active_credential_resolver() is None
    with credential_resolution(resolver):
        assert get_active_credential_resolver() is resolver
    assert get_active_credential_resolver() is None


def test_credential_resolution_allows_null_resolver() -> None:
    with credential_resolution(None) as active:
        assert active is None
        assert get_active_credential_resolver() is None


def test_node_decode_variables_injects_secret() -> None:
    vault = _create_vault_with_secret(secret="token")
    resolver = CredentialResolver(vault)
    node = SetVariableNode(
        name="store_secret",
        variables={"token": "[[telegram_bot]]"},
    )
    state = State({"results": {}, "messages": [], "inputs": {}})
    with credential_resolution(resolver):
        node.decode_variables(state)
    assert node.variables["token"] == "token"


def test_node_decode_variables_without_resolver_errors() -> None:
    node = SetVariableNode(
        name="store_secret",
        variables={"token": "[[telegram_bot]]"},
    )
    state = State({"results": {}, "messages": [], "inputs": {}})
    with pytest.raises(CredentialResolverUnavailableError):
        node.decode_variables(state)


def test_node_accepts_explicit_credential_reference() -> None:
    vault = _create_vault_with_secret(secret="token")
    resolver = CredentialResolver(vault)
    node = SetVariableNode(
        name="store_secret",
        variables={"token": credential_ref("telegram_bot")},
    )
    state = State({"results": {}, "messages": [], "inputs": {}})
    with credential_resolution(resolver):
        node.decode_variables(state)
    assert node.variables["token"] == "token"


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
    vault = _create_vault_with_secret(secret="token")
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
    vault = _create_vault_with_secret(secret="token")
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        value = resolver.resolve(CredentialReference("telegram_bot", ()))
        assert value == "token"


def test_resolver_raises_for_missing_oauth_attribute() -> None:
    vault = InMemoryCredentialVault()
    vault.create_credential(
        name="oauth_bot",
        provider="oauth",
        scopes=["bot"],
        secret="ignored",
        actor="tester",
        kind=CredentialKind.OAUTH,
        scope=CredentialScope.unrestricted(),
        oauth_tokens=OAuthTokenSecrets(access_token="token"),
    )
    resolver = CredentialResolver(vault)
    with credential_resolution(resolver):
        with pytest.raises(UnknownCredentialPayloadError):
            resolver.resolve(credential_ref("oauth_bot", "oauth.invalid"))
