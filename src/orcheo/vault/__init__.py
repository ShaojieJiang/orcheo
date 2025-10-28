"""Credential vault implementations with AES-256 encryption support."""

from __future__ import annotations
import secrets
import sqlite3
import threading
from collections.abc import Iterable, MutableMapping, Sequence
from pathlib import Path
from uuid import UUID
from orcheo.models import (
    AesGcmCredentialCipher,
    CredentialAccessContext,
    CredentialCipher,
    CredentialHealthStatus,
    CredentialIssuancePolicy,
    CredentialKind,
    CredentialMetadata,
    CredentialScope,
    CredentialTemplate,
    GovernanceAlertKind,
    OAuthTokenSecrets,
    SecretGovernanceAlert,
    SecretGovernanceAlertSeverity,
)


class VaultError(RuntimeError):
    """Base error type for vault operations."""


class CredentialNotFoundError(VaultError):
    """Raised when a credential cannot be found for the workflow."""


class CredentialTemplateNotFoundError(VaultError):
    """Raised when a credential template cannot be located."""


class GovernanceAlertNotFoundError(VaultError):
    """Raised when a governance alert cannot be located."""


class DuplicateCredentialNameError(VaultError):
    """Raised when attempting to create a credential with a duplicate name."""


class WorkflowScopeError(VaultError):
    """Raised when a credential scope denies access for the provided context."""


class RotationPolicyError(VaultError):
    """Raised when a rotation violates configured policies."""


class BaseCredentialVault:
    """Base helper that implements common credential vault workflows."""

    def __init__(self, *, cipher: CredentialCipher | None = None) -> None:
        """Initialize the vault with an encryption cipher."""
        self._cipher = cipher or AesGcmCredentialCipher(key=secrets.token_hex(32))

    @property
    def cipher(self) -> CredentialCipher:
        """Expose the credential cipher for services that need direct access."""
        return self._cipher

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
        if not isinstance(kind, CredentialKind):
            kind = CredentialKind(str(kind))
        metadata = CredentialMetadata.create(
            name=name,
            provider=provider,
            scopes=scopes,
            secret=secret,
            cipher=self._cipher,
            actor=actor,
            scope=scope,
            kind=kind,
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
        """Return credential metadata for a workflow."""
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
        for alert in list(self._iter_alerts()):
            if alert.credential_id == metadata.id:
                self._remove_alert(alert.id)

    def create_template(
        self,
        *,
        name: str,
        provider: str,
        scopes: Sequence[str],
        actor: str,
        description: str | None = None,
        scope: CredentialScope | None = None,
        kind: CredentialKind | str = CredentialKind.SECRET,
        issuance_policy: CredentialIssuancePolicy | None = None,
    ) -> CredentialTemplate:
        """Persist and return a new credential template."""
        if not isinstance(kind, CredentialKind):
            kind = CredentialKind(str(kind))
        template = CredentialTemplate.create(
            name=name,
            provider=provider,
            scopes=scopes,
            actor=actor,
            description=description,
            scope=scope,
            kind=kind,
            issuance_policy=issuance_policy,
        )
        self._persist_template(template)
        return template.model_copy(deep=True)

    def update_template(
        self,
        template_id: UUID,
        *,
        actor: str,
        name: str | None = None,
        description: str | None = None,
        scopes: Sequence[str] | None = None,
        scope: CredentialScope | None = None,
        kind: CredentialKind | str | None = None,
        issuance_policy: CredentialIssuancePolicy | None = None,
        context: CredentialAccessContext | None = None,
    ) -> CredentialTemplate:
        """Update template properties and persist the result."""
        template = self._get_template(template_id=template_id, context=context)
        changes: dict[str, object] = {}

        _update_template_simple_field(template, "name", name, changes)
        _update_template_simple_field(template, "description", description, changes)
        _update_template_scopes(template, scopes, changes)
        _update_template_scope(template, scope, changes)
        _update_template_kind(template, kind, changes)
        _update_template_policy(template, issuance_policy, changes)

        if changes:
            template.record_event(
                actor=actor,
                action="template_updated",
                metadata=changes,
            )
            self._persist_template(template)

        return template.model_copy(deep=True)

    def delete_template(
        self,
        template_id: UUID,
        *,
        context: CredentialAccessContext | None = None,
    ) -> None:
        """Remove a credential template from the vault."""
        self._get_template(template_id=template_id, context=context)
        self._remove_template(template_id)
        for alert in list(self._iter_alerts()):
            if alert.template_id == template_id:
                self._remove_alert(alert.id)

    def get_template(
        self,
        *,
        template_id: UUID,
        context: CredentialAccessContext | None = None,
    ) -> CredentialTemplate:
        """Return a credential template ensuring scope restrictions."""
        template = self._load_template(template_id)
        access_context = context or CredentialAccessContext()
        if not template.scope.allows(access_context):
            msg = "Credential template cannot be accessed with the provided context."
            raise WorkflowScopeError(msg)
        return template.model_copy(deep=True)

    def list_templates(
        self, *, context: CredentialAccessContext | None = None
    ) -> list[CredentialTemplate]:
        """Return credential templates available to the context."""
        access_context = context or CredentialAccessContext()
        return [
            template.model_copy(deep=True)
            for template in self._iter_templates()
            if template.scope.allows(access_context)
        ]

    def record_template_issuance(
        self,
        *,
        template_id: UUID,
        actor: str,
        credential_id: UUID,
        context: CredentialAccessContext | None = None,
    ) -> CredentialTemplate:
        """Append audit metadata on the template for an issuance event."""
        template = self._get_template(template_id=template_id, context=context)
        template.record_issuance(actor=actor, credential_id=credential_id)
        self._persist_template(template)
        return template.model_copy(deep=True)

    def record_alert(
        self,
        *,
        kind: GovernanceAlertKind,
        severity: SecretGovernanceAlertSeverity,
        message: str,
        actor: str,
        credential_id: UUID | None = None,
        template_id: UUID | None = None,
        context: CredentialAccessContext | None = None,
    ) -> SecretGovernanceAlert:
        """Persist a governance alert tied to a credential or template."""
        access_context = context or CredentialAccessContext()
        scope = CredentialScope.unrestricted()
        if credential_id is not None:
            metadata = self._get_metadata(
                credential_id=credential_id, context=access_context
            )
            scope = metadata.scope
            template_id = template_id or metadata.template_id
        elif template_id is not None:
            template = self._get_template(
                template_id=template_id, context=access_context
            )
            scope = template.scope

        existing = None
        for alert in self._iter_alerts():
            if not alert.scope.allows(access_context):
                continue
            if alert.is_acknowledged:
                continue
            if (
                alert.kind is kind
                and alert.credential_id == credential_id
                and alert.template_id == template_id
            ):
                existing = alert
                break

        if existing is not None:
            existing.severity = severity
            existing.message = message
            existing.record_event(
                actor=actor,
                action="alert_updated",
                metadata={"severity": severity.value, "message": message},
            )
            self._persist_alert(existing)
            return existing.model_copy(deep=True)

        alert = SecretGovernanceAlert.create(
            scope=scope,
            kind=kind,
            severity=severity,
            message=message,
            actor=actor,
            credential_id=credential_id,
            template_id=template_id,
        )
        self._persist_alert(alert)
        return alert.model_copy(deep=True)

    def list_alerts(
        self,
        *,
        context: CredentialAccessContext | None = None,
        include_acknowledged: bool = False,
    ) -> list[SecretGovernanceAlert]:
        """Return governance alerts permitted for the caller."""
        access_context = context or CredentialAccessContext()
        results: list[SecretGovernanceAlert] = []
        for alert in self._iter_alerts():
            if not alert.scope.allows(access_context):
                continue
            if not include_acknowledged and alert.is_acknowledged:
                continue
            results.append(alert.model_copy(deep=True))
        return results

    def acknowledge_alert(
        self,
        alert_id: UUID,
        *,
        actor: str,
        context: CredentialAccessContext | None = None,
    ) -> SecretGovernanceAlert:
        """Mark the specified alert as acknowledged."""
        alert = self._get_alert(alert_id=alert_id, context=context)
        alert.acknowledge(actor=actor)
        self._persist_alert(alert)
        return alert.model_copy(deep=True)

    def resolve_alerts_for_credential(
        self,
        credential_id: UUID,
        *,
        actor: str,
    ) -> list[SecretGovernanceAlert]:
        """Acknowledge all alerts associated with the credential."""
        resolved: list[SecretGovernanceAlert] = []
        for alert in self._iter_alerts():
            if alert.credential_id != credential_id or alert.is_acknowledged:
                continue
            alert.acknowledge(actor=actor)
            self._persist_alert(alert)
            resolved.append(alert.model_copy(deep=True))
        return resolved

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

    def _persist_metadata(
        self, metadata: CredentialMetadata
    ) -> None:  # pragma: no cover
        raise NotImplementedError

    def _load_metadata(
        self, credential_id: UUID
    ) -> CredentialMetadata:  # pragma: no cover
        raise NotImplementedError

    def _iter_metadata(self) -> Iterable[CredentialMetadata]:  # pragma: no cover
        raise NotImplementedError

    def _remove_credential(self, credential_id: UUID) -> None:  # pragma: no cover
        raise NotImplementedError

    def _persist_template(self, template: CredentialTemplate) -> None:
        raise NotImplementedError  # pragma: no cover

    def _load_template(self, template_id: UUID) -> CredentialTemplate:
        raise NotImplementedError  # pragma: no cover

    def _iter_templates(self) -> Iterable[CredentialTemplate]:
        raise NotImplementedError  # pragma: no cover

    def _remove_template(self, template_id: UUID) -> None:
        raise NotImplementedError  # pragma: no cover

    def _persist_alert(self, alert: SecretGovernanceAlert) -> None:
        raise NotImplementedError  # pragma: no cover

    def _load_alert(self, alert_id: UUID) -> SecretGovernanceAlert:
        raise NotImplementedError  # pragma: no cover

    def _iter_alerts(self) -> Iterable[SecretGovernanceAlert]:  # pragma: no cover
        raise NotImplementedError

    def _remove_alert(self, alert_id: UUID) -> None:  # pragma: no cover
        raise NotImplementedError

    def _get_template(
        self,
        *,
        template_id: UUID,
        context: CredentialAccessContext | None = None,
    ) -> CredentialTemplate:
        template = self._load_template(template_id)
        access_context = context or CredentialAccessContext()
        if not template.scope.allows(access_context):
            msg = "Credential template cannot be accessed with the provided context."
            raise WorkflowScopeError(msg)
        return template

    def _get_alert(
        self,
        *,
        alert_id: UUID,
        context: CredentialAccessContext | None = None,
    ) -> SecretGovernanceAlert:
        alert = self._load_alert(alert_id)
        if context is None:
            if not alert.scope.is_unrestricted():
                msg = "Governance alert requires access context matching its scope."
                raise WorkflowScopeError(msg)
            access_context = CredentialAccessContext()
        else:
            access_context = context
        if not alert.scope.allows(access_context):
            msg = "Governance alert cannot be accessed with the provided context."
            raise WorkflowScopeError(msg)
        return alert


class InMemoryCredentialVault(BaseCredentialVault):
    """In-memory credential vault used for tests and local workflows."""

    def __init__(self, *, cipher: CredentialCipher | None = None) -> None:
        """Create an ephemeral in-memory vault instance."""
        super().__init__(cipher=cipher)
        self._store: dict[UUID, CredentialMetadata] = {}
        self._templates: dict[UUID, CredentialTemplate] = {}
        self._alerts: dict[UUID, SecretGovernanceAlert] = {}

    def _persist_metadata(self, metadata: CredentialMetadata) -> None:
        normalized = metadata.name.casefold()
        for stored_id, stored in self._store.items():
            if stored_id == metadata.id:
                continue
            if stored.name.casefold() == normalized:
                msg = f"Credential name '{metadata.name}' is already in use."
                raise DuplicateCredentialNameError(msg)
        self._store[metadata.id] = metadata.model_copy(deep=True)

    def _load_metadata(self, credential_id: UUID) -> CredentialMetadata:
        try:
            return self._store[credential_id].model_copy(deep=True)
        except KeyError as exc:
            msg = "Credential was not found."
            raise CredentialNotFoundError(msg) from exc

    def _iter_metadata(self) -> Iterable[CredentialMetadata]:
        for metadata in self._store.values():
            yield metadata.model_copy(deep=True)

    def _remove_credential(self, credential_id: UUID) -> None:
        try:
            del self._store[credential_id]
        except KeyError as exc:
            msg = "Credential was not found."
            raise CredentialNotFoundError(msg) from exc

    def _persist_template(self, template: CredentialTemplate) -> None:
        self._templates[template.id] = template.model_copy(deep=True)

    def _load_template(self, template_id: UUID) -> CredentialTemplate:
        try:
            return self._templates[template_id].model_copy(deep=True)
        except KeyError as exc:
            msg = "Credential template was not found."
            raise CredentialTemplateNotFoundError(msg) from exc

    def _iter_templates(self) -> Iterable[CredentialTemplate]:
        for template in self._templates.values():
            yield template.model_copy(deep=True)

    def _remove_template(self, template_id: UUID) -> None:
        try:
            del self._templates[template_id]
        except KeyError as exc:
            msg = "Credential template was not found."
            raise CredentialTemplateNotFoundError(msg) from exc

    def _persist_alert(self, alert: SecretGovernanceAlert) -> None:
        self._alerts[alert.id] = alert.model_copy(deep=True)

    def _load_alert(self, alert_id: UUID) -> SecretGovernanceAlert:
        try:
            return self._alerts[alert_id].model_copy(deep=True)
        except KeyError as exc:
            msg = "Governance alert was not found."
            raise GovernanceAlertNotFoundError(msg) from exc

    def _iter_alerts(self) -> Iterable[SecretGovernanceAlert]:
        for alert in self._alerts.values():
            yield alert.model_copy(deep=True)

    def _remove_alert(self, alert_id: UUID) -> None:
        self._alerts.pop(alert_id, None)


class FileCredentialVault(BaseCredentialVault):
    """File-backed credential vault stored in a SQLite database."""

    def __init__(
        self, path: str | Path, *, cipher: CredentialCipher | None = None
    ) -> None:
        """Create a SQLite-backed credential vault."""
        super().__init__(cipher=cipher)
        self._path = Path(path).expanduser()
        self._lock = threading.Lock()
        self._initialize()

    def _initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_credentials_workflow
                    ON credentials(workflow_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS credential_templates (
                    id TEXT PRIMARY KEY,
                    scope_hint TEXT NOT NULL,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_templates_scope
                    ON credential_templates(scope_hint)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS governance_alerts (
                    id TEXT PRIMARY KEY,
                    scope_hint TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_alerts_scope
                    ON governance_alerts(scope_hint)
                """
            )
            conn.commit()

    def _persist_metadata(self, metadata: CredentialMetadata) -> None:
        payload = metadata.model_dump_json()
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                """
                SELECT id
                  FROM credentials
                 WHERE lower(name) = lower(?)
                """,
                (metadata.name,),
            )
            rows = [row[0] for row in cursor.fetchall()]
            duplicates = [row_id for row_id in rows if row_id != str(metadata.id)]
            if duplicates:
                msg = f"Credential name '{metadata.name}' is already in use."
                raise DuplicateCredentialNameError(msg)
            conn.execute(
                """
                INSERT OR REPLACE INTO credentials (
                    id,
                    workflow_id,
                    name,
                    provider,
                    created_at,
                    updated_at,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(metadata.id),
                    metadata.scope.scope_hint(),
                    metadata.name,
                    metadata.provider,
                    metadata.created_at.isoformat(),
                    metadata.updated_at.isoformat(),
                    payload,
                ),
            )
            conn.commit()

    def _load_metadata(self, credential_id: UUID) -> CredentialMetadata:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                "SELECT payload FROM credentials WHERE id = ?",
                (str(credential_id),),
            )
            row = cursor.fetchone()
        if row is None:
            msg = "Credential was not found."
            raise CredentialNotFoundError(msg)
        return CredentialMetadata.model_validate_json(row[0])

    def _iter_metadata(self) -> Iterable[CredentialMetadata]:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                """
                SELECT payload
                  FROM credentials
              ORDER BY created_at ASC
                """
            )
            rows = cursor.fetchall()
        for row in rows:
            yield CredentialMetadata.model_validate_json(row[0])

    def _remove_credential(self, credential_id: UUID) -> None:
        with self._lock, sqlite3.connect(self._path) as conn:
            deleted = conn.execute(
                "DELETE FROM credentials WHERE id = ?",
                (str(credential_id),),
            ).rowcount
            conn.commit()
        if deleted == 0:
            msg = "Credential was not found."
            raise CredentialNotFoundError(msg)

    def _persist_template(self, template: CredentialTemplate) -> None:
        payload = template.model_dump_json()
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO credential_templates (
                    id,
                    scope_hint,
                    name,
                    provider,
                    created_at,
                    updated_at,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(template.id),
                    template.scope.scope_hint(),
                    template.name,
                    template.provider,
                    template.created_at.isoformat(),
                    template.updated_at.isoformat(),
                    payload,
                ),
            )
            conn.commit()

    def _load_template(self, template_id: UUID) -> CredentialTemplate:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                "SELECT payload FROM credential_templates WHERE id = ?",
                (str(template_id),),
            )
            row = cursor.fetchone()
        if row is None:
            msg = "Credential template was not found."
            raise CredentialTemplateNotFoundError(msg)
        return CredentialTemplate.model_validate_json(row[0])

    def _iter_templates(self) -> Iterable[CredentialTemplate]:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                """
                SELECT payload
                  FROM credential_templates
              ORDER BY created_at ASC
                """
            )
            rows = cursor.fetchall()
        for row in rows:
            yield CredentialTemplate.model_validate_json(row[0])

    def _remove_template(self, template_id: UUID) -> None:
        with self._lock, sqlite3.connect(self._path) as conn:
            deleted = conn.execute(
                "DELETE FROM credential_templates WHERE id = ?",
                (str(template_id),),
            ).rowcount
            conn.commit()
        if deleted == 0:
            msg = "Credential template was not found."
            raise CredentialTemplateNotFoundError(msg)

    def _persist_alert(self, alert: SecretGovernanceAlert) -> None:
        payload = alert.model_dump_json()
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO governance_alerts (
                    id,
                    scope_hint,
                    acknowledged,
                    created_at,
                    updated_at,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(alert.id),
                    alert.scope.scope_hint(),
                    1 if alert.is_acknowledged else 0,
                    alert.created_at.isoformat(),
                    alert.updated_at.isoformat(),
                    payload,
                ),
            )
            conn.commit()

    def _load_alert(self, alert_id: UUID) -> SecretGovernanceAlert:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                "SELECT payload FROM governance_alerts WHERE id = ?",
                (str(alert_id),),
            )
            row = cursor.fetchone()
        if row is None:
            msg = "Governance alert was not found."
            raise GovernanceAlertNotFoundError(msg)
        return SecretGovernanceAlert.model_validate_json(row[0])

    def _iter_alerts(self) -> Iterable[SecretGovernanceAlert]:
        with self._lock, sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                """
                SELECT payload
                  FROM governance_alerts
              ORDER BY created_at ASC
                """
            )
            rows = cursor.fetchall()
        for row in rows:
            yield SecretGovernanceAlert.model_validate_json(row[0])

    def _remove_alert(self, alert_id: UUID) -> None:
        with self._lock, sqlite3.connect(self._path) as conn:
            conn.execute(
                "DELETE FROM governance_alerts WHERE id = ?",
                (str(alert_id),),
            )
            conn.commit()


def _update_template_simple_field(
    template: CredentialTemplate,
    attr: str,
    value: str | None,
    changes: dict[str, object],
) -> None:
    if value is None:
        return
    current = getattr(template, attr)
    if current == value:
        return
    changes[attr] = {"from": current, "to": value}
    setattr(template, attr, value)


def _update_template_scopes(
    template: CredentialTemplate,
    scopes: Sequence[str] | None,
    changes: dict[str, object],
) -> None:
    if scopes is None:
        return
    normalized = list(scopes)
    if normalized == template.scopes:
        return
    changes["scopes"] = {
        "from": list(template.scopes),
        "to": normalized,
    }
    template.scopes = normalized


def _update_template_scope(
    template: CredentialTemplate,
    scope: CredentialScope | None,
    changes: dict[str, object],
) -> None:
    if scope is None or scope == template.scope:
        return
    changes["scope"] = {
        "from": template.scope.model_dump(),
        "to": scope.model_dump(),
    }
    template.scope = scope


def _normalize_template_kind(
    kind: CredentialKind | str | None,
) -> CredentialKind | None:
    if kind is None:
        return None
    if isinstance(kind, CredentialKind):
        return kind
    return CredentialKind(str(kind))


def _update_template_kind(
    template: CredentialTemplate,
    kind: CredentialKind | str | None,
    changes: dict[str, object],
) -> None:
    new_kind = _normalize_template_kind(kind)
    if new_kind is None or new_kind is template.kind:
        return
    changes["kind"] = {
        "from": template.kind.value,
        "to": new_kind.value,
    }
    template.kind = new_kind


def _update_template_policy(
    template: CredentialTemplate,
    issuance_policy: CredentialIssuancePolicy | None,
    changes: dict[str, object],
) -> None:
    if issuance_policy is None:
        return
    if issuance_policy.model_dump() == template.issuance_policy.model_dump():
        return
    changes["issuance_policy"] = {
        "from": template.issuance_policy.model_dump(),
        "to": issuance_policy.model_dump(),
    }
    template.issuance_policy = issuance_policy


__all__ = [
    "VaultError",
    "CredentialNotFoundError",
    "CredentialTemplateNotFoundError",
    "GovernanceAlertNotFoundError",
    "DuplicateCredentialNameError",
    "WorkflowScopeError",
    "RotationPolicyError",
    "BaseCredentialVault",
    "InMemoryCredentialVault",
    "FileCredentialVault",
]
