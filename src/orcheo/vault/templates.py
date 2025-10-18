"""Credential template service wired to the credential vault."""

from __future__ import annotations
from collections.abc import Callable, Mapping
from orcheo.models import (
    CredentialGovernanceAlert,
    CredentialMetadata,
    CredentialTemplate,
    CredentialTemplateCatalog,
    build_default_template_catalog,
    default_secret_factory,
)
from orcheo.vault import BaseCredentialVault


class CredentialTemplateService:
    """Expose credential templates and issuance operations."""

    def __init__(
        self,
        vault: BaseCredentialVault,
        catalog: CredentialTemplateCatalog | None = None,
    ) -> None:
        """Create the template service bound to the provided vault."""
        self._vault = vault
        self._catalog = catalog or build_default_template_catalog()

    @property
    def templates(self) -> list[CredentialTemplate]:
        """Return registered templates."""
        return self._catalog.as_list()

    def get_template(self, provider: str) -> CredentialTemplate:
        """Return a single template by provider slug."""
        return self._catalog.get(provider)

    def issue(
        self,
        provider: str,
        *,
        values: Mapping[str, str],
        actor: str,
        secret_factory: Callable[[Mapping[str, str]], str] | None = None,
    ) -> tuple[CredentialMetadata, list[CredentialGovernanceAlert]]:
        """Issue a credential for the provider using the template definition."""
        factory = secret_factory or default_secret_factory
        return self._catalog.issue(
            provider,
            values=values,
            actor=actor,
            secret_factory=factory,
            vault_create=lambda **kwargs: self._vault.create_credential(**kwargs),
        )


__all__ = ["CredentialTemplateService"]
