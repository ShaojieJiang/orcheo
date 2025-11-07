"""Credential-focused operations shared by vault implementations."""

from __future__ import annotations
from collections.abc import Iterable, MutableMapping, Sequence
from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID
from orcheo.models import (
    CredentialAccessContext,
    CredentialHealthStatus,
    CredentialKind,
    CredentialMetadata,
    CredentialScope,
    OAuthTokenSecrets,
)
from orcheo.vault.errors import RotationPolicyError, WorkflowScopeError


if TYPE_CHECKING:
    from orcheo.models import (  # pragma: no cover
        CredentialCipher,
        SecretGovernanceAlert,
    )

    class _AlertStore(Protocol):
        def _iter_alerts(self) -> Iterable[SecretGovernanceAlert]: ...

        def _remove_alert(self, alert_id: UUID) -> None: ...


class CredentialOperationsMixin:
    """Mixin implementing credential CRUD operations for vaults."""

    _cipher: CredentialCipher

    def create_credential(
        self,
        *,
        name: str,
        provider: str,
        scopes: Sequence[str],
        secret: str,
        actor: str,
        scope: CredentialScope | None = None,
        kind: CredentialKind | str = CredentialKind.SECRET,
        oauth_tokens: OAuthTokenSecrets | None = None,
        template_id: UUID | None = None,
    ) -> CredentialMetadata:
        """Encrypt and persist a new credential."""
        normalized_kind = kind
        if not isinstance(normalized_kind, CredentialKind):
            normalized_kind = CredentialKind(str(kind))
        metadata = CredentialMetadata.create(
            name=name,
            provider=provider,
            scopes=scopes,
            secret=secret,
            cipher=self._cipher,
            actor=actor,
            scope=scope,
            kind=normalized_kind,
            oauth_tokens=oauth_tokens,
            template_id=template_id,
        )
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def rotate_secret(
        self,
        *,
        credential_id: UUID,
        secret: str,
        actor: str,
        context: CredentialAccessContext | None = None,
    ) -> CredentialMetadata:
        """Rotate an existing credential secret enforcing policy constraints."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        current_secret = metadata.reveal(cipher=self._cipher)
        if current_secret == secret:
            msg = "Rotated secret must differ from the previous value."
            raise RotationPolicyError(msg)
        metadata.rotate_secret(secret=secret, cipher=self._cipher, actor=actor)
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def update_oauth_tokens(
        self,
        *,
        credential_id: UUID,
        tokens: OAuthTokenSecrets | None,
        actor: str | None = None,
        context: CredentialAccessContext | None = None,
    ) -> CredentialMetadata:
        """Update OAuth tokens associated with the credential."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        metadata.update_oauth_tokens(
            cipher=self._cipher, tokens=tokens, actor=actor or "system"
        )
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def mark_health(
        self,
        *,
        credential_id: UUID,
        status: CredentialHealthStatus,
        reason: str | None,
        actor: str | None = None,
        context: CredentialAccessContext | None = None,
    ) -> CredentialMetadata:
        """Persist the latest health evaluation result for the credential."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        metadata.mark_health(status=status, reason=reason, actor=actor)
        self._persist_metadata(metadata)
        return metadata.model_copy(deep=True)

    def reveal_secret(
        self,
        *,
        credential_id: UUID,
        context: CredentialAccessContext | None = None,
    ) -> str:
        """Return the decrypted secret for the credential."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        return metadata.reveal(cipher=self._cipher)

    def list_credentials(
        self, *, context: CredentialAccessContext | None = None
    ) -> list[CredentialMetadata]:
        """Return credential metadata permitted for the workflow context."""
        access_context = context or CredentialAccessContext()
        return [
            item.model_copy(deep=True)
            for item in self._iter_metadata()
            if item.scope.allows(access_context)
        ]

    def describe_credentials(
        self, *, context: CredentialAccessContext | None = None
    ) -> list[MutableMapping[str, object]]:
        """Return masked representations suitable for logging."""
        access_context = context or CredentialAccessContext()
        return [
            item.redact()
            for item in self._iter_metadata()
            if item.scope.allows(access_context)
        ]

    def delete_credential(
        self,
        credential_id: UUID,
        *,
        context: CredentialAccessContext | None = None,
    ) -> None:
        """Remove a credential and associated governance alerts from the vault."""
        metadata = self._get_metadata(credential_id=credential_id, context=context)
        self._remove_credential(metadata.id)
        alert_store = cast("_AlertStore", self)
        for alert in list(alert_store._iter_alerts()):
            if alert.credential_id == metadata.id:
                alert_store._remove_alert(alert.id)

    def _get_metadata(
        self,
        *,
        credential_id: UUID,
        context: CredentialAccessContext | None = None,
    ) -> CredentialMetadata:
        metadata = self._load_metadata(credential_id)
        access_context = context or CredentialAccessContext()
        if not metadata.scope.allows(access_context):
            msg = "Credential cannot be accessed with the provided context."
            raise WorkflowScopeError(msg)
        return metadata

    def _persist_metadata(self, metadata: CredentialMetadata) -> None:
        """Persist credential metadata to storage."""
        raise NotImplementedError  # pragma: no cover

    def _load_metadata(self, credential_id: UUID) -> CredentialMetadata:
        """Load credential metadata from storage."""
        raise NotImplementedError  # pragma: no cover

    def _iter_metadata(self) -> Iterable[CredentialMetadata]:
        """Iterate over stored credential metadata."""
        raise NotImplementedError  # pragma: no cover

    def _remove_credential(self, credential_id: UUID) -> None:
        """Remove credential metadata from storage."""
        raise NotImplementedError  # pragma: no cover
