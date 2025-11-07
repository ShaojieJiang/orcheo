"""Shared helpers for runtime credential tests."""

from __future__ import annotations
from orcheo.models import CredentialScope
from orcheo.vault import InMemoryCredentialVault


def create_vault_with_secret(secret: str = "s3cret") -> InMemoryCredentialVault:
    """Create a vault seeded with a single unrestricted credential."""
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
